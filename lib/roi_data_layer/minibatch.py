# --------------------------------------------------------
# Fast R-CNN
# Copyright (c) 2015 Microsoft
# Licensed under The MIT License [see LICENSE for details]
# Written by Ross Girshick and Xinlei Chen - Exteded by Lukas Tuggener
# --------------------------------------------------------

"""Compute minibatch blobs for training a Fast R-CNN network."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import numpy.random as npr
import cv2
from main.config import cfg
from utils.blob import prep_im_for_blob, im_list_to_blob
from datasets.fcn_groundtruth import objectness_energy, show_image, objectness_energy_high_dym, fcn_class_labels, fcn_bbox_labels

def get_minibatch(roidb, num_classes, batch_size):
  """Given a roidb, construct a minibatch sampled from it."""
  num_images = len(roidb)
  # Sample random scales to use for each image in this batch
  random_scale_inds = npr.randint(0, high=len(cfg.TRAIN.SCALES),
                  size=num_images)
  assert(batch_size % num_images == 0), \
    'num_images ({}) must divide BATCH_SIZE ({})'. \
    format(num_images, cfg.TRAIN.BATCH_SIZE)

  # Get the input image blob, formatted for caffe
  im_blob, im_scales, crop_box = _get_image_blob(roidb, random_scale_inds)

  blobs = {'data': im_blob}

  assert len(im_scales) == 1, "Single batch only"
  assert len(roidb) == 1, "Single batch only"
  
  # gt boxes: (x1, y1, x2, y2, cls)
  if cfg.TRAIN.USE_ALL_GT:
    # Include all ground truth boxes
    gt_inds = np.where(roidb[0]['gt_classes'] != 0)[0]
  else:
    # For the COCO ground truth boxes, exclude the  ones that are ''iscrowd''
    gt_inds = np.where(roidb[0]['gt_classes'] != 0 & np.all(roidb[0]['gt_overlaps'].toarray() > -1.0, axis=1))[0]
  gt_boxes = np.empty((len(gt_inds), 5), dtype=np.float32)
  bad_coords = np.zeros(len(gt_inds), dtype=np.bool)
  if cfg.TRAIN.CROP:

    #scale Coords
    gt_boxes[:, 0:4] = roidb[0]['boxes'][gt_inds, :] * im_scales[0]

    gt_boxes[:, 0:4] = gt_boxes[:, 0:4] - [crop_box[0][1], crop_box[0][0], crop_box[0][1], crop_box[0][0]]

                 # lower coords above 0
    bad_coords = np.sum(gt_boxes[:, 0:4][:, [0, 1]] >= 0, 1) + np.sum(gt_boxes[:, 0:4][:, [2, 3]] < cfg.TRAIN.MAX_SIZE, 1) < 4


  else:
    gt_boxes[:, 0:4] = roidb[0]['boxes'][gt_inds, :] * im_scales[0]


  gt_boxes[:, 4] = roidb[0]['gt_classes'][gt_inds]
  gt_boxes = gt_boxes[bad_coords==False]

  # build additional gt for FCN
  if cfg.TRAIN.BUILD_FCN:
    #show_image(im_blob, gt_boxes, gt=True)
    blobs['dws_energy'] = objectness_energy(im_blob, gt_boxes)
    #objectness_energy_high_dym(im_blob, gt_boxes, num_classes)
    blobs["class_map"] = fcn_class_labels(im_blob, gt_boxes)
    blobs["bbox_fcn"] = fcn_bbox_labels(im_blob, gt_boxes)


  blobs['gt_boxes'] = gt_boxes
  blobs['im_info'] = np.array(
    [[im_blob.shape[1], im_blob.shape[2], im_scales[0]]],
    dtype=np.float32)

  return blobs

def _get_image_blob(roidb, scale_inds):
  """Builds an input blob from the images in the roidb at the specified
  scales.
  """
  num_images = len(roidb)
  processed_ims = []
  im_scales = []
  crop_box = []

  for i in range(num_images):
    im = cv2.imread(roidb[i]['image'])
    if roidb[i]['flipped']:
      im = im[:, ::-1, :]
    target_size = cfg.TRAIN.SCALES[scale_inds[i]]
    im, im_scale, im_crop_box = prep_im_for_blob(im, cfg.PIXEL_MEANS, target_size,
                    cfg.TRAIN.MAX_SIZE, cfg.TRAIN.CROP, cfg.TRAIN.CROP_SCALE)

    crop_box.append(im_crop_box)
    im_scales.append(im_scale)
    processed_ims.append(im)

  # Create a blob to hold the input images
  blob = im_list_to_blob(processed_ims)

  return blob, im_scales, crop_box
