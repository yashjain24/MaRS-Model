# USAGE
# python object_movement.py --video object_tracking_example.mp4
# python object_movement.py

# import the necessary packages
from collections import deque
import math
import numpy as np
from numpy import *
import argparse
import imutils
import cv2
import serial


ser=serial.Serial('/dev/ttyACM0',9600)
# construct the argument parse and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-v", "--video",
	help="path to the (optional) video file")
ap.add_argument("-b", "--buffer", type=int, default=32,
	help="max buffer size")
args = vars(ap.parse_args())

# define the lower and upper boundaries of the "green"
# ball in the HSV color space
yellowLower = (23,41,133)
yellowUpper = (40,150,255)

# initialize the list of tracked points, the frame counter,
# and the coordinate deltas
pts = deque(maxlen=args["buffer"])
counter = 0
(dX, dY) = (0, 0)
direction = ""

# if a video path was not supplied, grab the reference
# to the webcam
if not args.get("video", False):
	camera = cv2.VideoCapture(-1)

# otherwise, grab a reference to the video file
else:
	camera = cv2.VideoCapture(args["video"])

count=0
edges=[0,0,0,0]
def perp( a ) :
    b = empty_like(a)
    b[0] = -a[1]
    b[1] = a[0]
    return b

def seg_intersect(a1,a2, b1,b2) :
    da = a2-a1
    db = b2-b1
    dp = a1-b1
    dap = perp(da)
    denom = dot( dap, db)
    num = dot( dap, dp )
    return (num / denom.astype(float))*db + b1


def order_points(pts):
	# initialzie a list of coordinates that will be ordered
	# such that the first entry in the list is the top-left,
	# the second entry is the top-right, the third is the
	# bottom-right, and the fourth is the bottom-left
	rect = np.zeros((4, 2), dtype = "float32")

	# the top-left point will have the smallest sum, whereas
	# the bottom-right point will have the largest sum
	s = np.sum(pts,axis = 1)
	rect[0] = pts[np.argmin(s)]
	rect[2] = pts[np.argmax(s)]

	# now, compute the difference between the points, the
	# top-right point will have the smallest difference,
	# whereas the bottom-left will have the largest difference
	diff = np.diff(pts, axis = 1)
	rect[1] = pts[np.argmin(diff)]
	rect[3] = pts[np.argmax(diff)]

	# return the ordered coordinates
	return rect

def four_point_transform(image, pts):
	# obtain a consistent order of the points and unpack them
	# individually
	rect = order_points(pts)
	(tl, tr, br, bl) = rect

	# compute the width of the new image, which will be the
	# maximum distance between bottom-right and bottom-left
	# x-coordiates or the top-right and top-left x-coordinates
	widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
	widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
	maxWidth = max(int(widthA), int(widthB))

	# compute the height of the new image, which will be the
	# maximum distance between the top-right and bottom-right
	# y-coordinates or the top-left and bottom-left y-coordinates
	heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
	heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
	maxHeight = max(int(heightA), int(heightB))

	# now that we have the dimensions of the new image, construct
	# the set of destination points to obtain a "birds eye view",
	# (i.e. top-down view) of the image, again specifying points
	# in the top-left, top-right, bottom-right, and bottom-left
	# order
	dst = np.array([
		[0, 0],
		[1000, 0],
		[1000, 600],
		[0, 600]], dtype = "float32")

	# compute the perspective transform matrix and then apply it
	M = cv2.getPerspectiveTransform(rect, dst)
	warped = cv2.warpPerspective(image, M, (1000, 600))

	# return the warped image
	return warped

# keep looping
while True:
	# grab the current frame
	(grabbed, frame) = camera.read()

	# if we are viewing a video and we did not grab a frame,
	# then we have reached the end of the video
	if args.get("video") and not grabbed:
		break

	# resize the frame, blur it, and convert it to the HSV
	# color space
	frame = imutils.resize(frame, width=800)
	# blurred = cv2.GaussianBlur(frame, (11, 11), 0)
	hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

	# construct a mask for the color "green", then perform
	# a series of dilations and erosions to remove any small
	# blobs left in the mask
	mask = cv2.inRange(hsv, yellowLower, yellowUpper)
	mask = cv2.erode(mask, None, iterations=2)
	mask = cv2.dilate(mask, None, iterations=2)


	# find contours in the mask and initialize the current
	# (x, y) center of the ball
	cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL,
		cv2.CHAIN_APPROX_SIMPLE)[-2]
	center = None

	# only proceed if at least one contour was found
	if len(cnts) > 0:
		# find the largest contour in the mask, then use
		# it to compute the minimum enclosing circle and
		# centroid
		c = max(cnts, key=cv2.contourArea)
		((x, y), radius) = cv2.minEnclosingCircle(c)
		M = cv2.moments(c)
		center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))


	# loop over the set of tracked points
	for i in np.arange(1, len(pts)):
		# if either of the tracked points are None, ignore
		# them
		if pts[i - 1] is None or pts[i] is None:
			continue

		# check to see if enough points have been accumulated in
		# the buffer
		if counter >= 10 and i == 1 and pts[-10] is not None:
			# compute the difference between the x and y
			# coordinates and re-initialize the direction
			# text variables
			dX = pts[-10][0] - pts[i][0]
			dY = pts[-10][1] - pts[i][1]
			(dirX, dirY) = ("", "")

			# ensure there is significant movement in the
			# x-direction
			if np.abs(dX) > 20:
				dirX = "East" if np.sign(dX) == 1 else "West"

			# ensure there is significant movement in the
			# y-direction
			if np.abs(dY) > 20:
				dirY = "North" if np.sign(dY) == 1 else "South"

			# handle when both directions are non-empty
			if dirX != "" and dirY != "":
				direction = "{}-{}".format(dirY, dirX)

			# otherwise, only one direction is non-empty
			else:
				direction = dirX if dirX != "" else dirY

		# otherwise, compute the thickness of the line and
		# draw the connecting lines
		thickness = int(np.sqrt(args["buffer"] / float(i + 1)) * 2.5)
		cv2.line(frame, pts[i - 1], pts[i], (0, 0, 255), thickness)

	# show the movement deltas and the direction of movement on
	# the frame
	cv2.putText(frame, direction, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
		0.65, (0, 0, 255), 3)
	cv2.putText(frame, "dx: {}, dy: {}".format(dX, dY),
		(10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX,
		0.35, (0, 0, 255), 1)

	if (count<4):
		cv2.imshow("Frame", frame)
		key = cv2.waitKey(5) & 0xFF
		counter += 1

		# only proceed if the radius meets a minimum size
		if radius > 10:
			# draw the circle and centroid on the frame,
			# then update the list of tracked points
			cv2.circle(frame, (int(x), int(y)), int(radius),
				(0, 255, 255), 2)
			cv2.circle(frame, center, 5, (0, 0, 255), -1)
			pts.appendleft(center)

	if(count>3):

	#	str1 = ",".join(str(e) for e in edges )
	#	str1=("[")+str1+("]")
	#	pts = np.array(eval(args[str1]), dtype = "float32")
		wimage=four_point_transform(frame, edges)
		A=array( edges[0])
		B=array( edges[1])
		C=array( edges[2])
		D=array( edges[3])

		seg_intersect(A,B,C,D)

		# show the frame to our screen and increment the frame counter
		cv2.imshow("WFrame", wimage)
		key = cv2.waitKey(100) & 0xFF
		counter += 1

		# only proceed if the radius meets a minimum size
		if radius > 0:
			# draw the circle and centroid on the frame,
			# then update the list of tracked points
			cv2.circle(wimage, (int(x), int(y)), int(radius),
				(0, 255, 255), 2)
			cv2.circle(wimage, center, 5, (0, 0, 255), -1)
			pts.appendleft(center)
			K =center

		E = seg_intersect(A,B,C,D)
		F = seg_intersect(D,A,B,C)


		P = seg_intersect(B,C,E,K)
		Q = seg_intersect(A,D,E,K)


		R = seg_intersect(A,B,F,K)
		S = seg_intersect(D,C,F,K)
		h1=math.fabs(np.linalg.norm(P - K))
		h2=math.fabs(np.linalg.norm(Q - P))

		h3=math.fabs(np.linalg.norm(R -K))
		h4=math.fabs(np.linalg.norm(S - R))

		y= math.fabs((h1*600)/h2)
		x= math.fabs((h3*1000)/h4)
		Ncentre = [x,y]

	# if the 'q' key is pressed, stop the loop
	if key == ord("q"):
		break

	if key == ord("n"):
		print (center)
		ser.write
	if key == ord("c"):
		print (center)
		print (Ncentre)
		x1=str(int(x))
		y1=str(int(y))
		send=x1+' '+y1
		ser.write(send)
		
	if key == ord("k"):
		if(count<4):
			edges[count]= [center[0],center[1]]
			print (edges)
			count+=1

# cleanup the camera and close any open windows
camera.release()
cv2.destroyAllWindows()
