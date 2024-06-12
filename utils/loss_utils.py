#
# Copyright (C) 2023, Inria
# GRAPHDECO research group, https://team.inria.fr/graphdeco
# All rights reserved.
#
# This software is free for non-commercial, research and evaluation use 
# under the terms of the LICENSE.md file.
#
# For inquiries contact  george.drettakis@inria.fr
#

import torch
import torch.nn.functional as F
from torch.autograd import Variable
from math import exp

def psnr(img1, img2):
    mse = F.mse_loss(img1, img2)
    return 20 * torch.log10(1.0 / torch.sqrt(mse))

def gaussian(window_size, sigma):
    gauss = torch.Tensor([exp(-(x - window_size // 2) ** 2 / float(2 * sigma ** 2)) for x in range(window_size)])
    return gauss / gauss.sum()

def create_window(window_size, channel):
    _1D_window = gaussian(window_size, 1.5).unsqueeze(1)
    _2D_window = _1D_window.mm(_1D_window.t()).float().unsqueeze(0).unsqueeze(0)
    window = Variable(_2D_window.expand(channel, 1, window_size, window_size).contiguous())
    return window

def ssim(img1, img2, window_size=11, size_average=True):
    channel = img1.size(-3)
    window = create_window(window_size, channel)

    if img1.is_cuda:
        window = window.cuda(img1.get_device())
    window = window.type_as(img1)

    return _ssim(img1, img2, window, window_size, channel, size_average)

def _ssim(img1, img2, window, window_size, channel, size_average=True):
    mu1 = F.conv2d(img1, window, padding=window_size // 2, groups=channel)
    mu2 = F.conv2d(img2, window, padding=window_size // 2, groups=channel)

    mu1_sq = mu1.pow(2)
    mu2_sq = mu2.pow(2)
    mu1_mu2 = mu1 * mu2

    sigma1_sq = F.conv2d(img1 * img1, window, padding=window_size // 2, groups=channel) - mu1_sq
    sigma2_sq = F.conv2d(img2 * img2, window, padding=window_size // 2, groups=channel) - mu2_sq
    sigma12 = F.conv2d(img1 * img2, window, padding=window_size // 2, groups=channel) - mu1_mu2

    C1 = 0.01 ** 2
    C2 = 0.03 ** 2

    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))

    if size_average:
        return ssim_map.mean()
    else:
        return ssim_map.mean(1).mean(1).mean(1)
    
def tv_loss(depth):
    c, h, w = depth.shape[0], depth.shape[1], depth.shape[2]
    count_h = c * (h - 1) * w
    count_w = c * h * (w - 1)
    h_tv = torch.square(depth[..., 1:, :] - depth[..., :h-1, :]).sum()
    w_tv = torch.square(depth[..., :, 1:] - depth[..., :, :w-1]).sum()
    return 2 * (h_tv / count_h + w_tv / count_w)

def multi_scale_depth_loss(predicted_depth, gt_depth, scales=[1, 2, 4]):
    loss = 0.0
    for scale in scales:
        scaled_predicted_depth = F.interpolate(predicted_depth, scale_factor=1/scale, mode='bilinear', align_corners=True)
        scaled_gt_depth = F.interpolate(gt_depth, scale_factor=1/scale, mode='bilinear', align_corners=True)
        if scaled_predicted_depth.size() != scaled_gt_depth.size():
            scaled_gt_depth = scaled_gt_depth[:, :scaled_predicted_depth.size(1), :, :]
        loss += F.l1_loss(scaled_predicted_depth, scaled_gt_depth)
    return loss

def calculate_depth_difference(predicted_depth, gt_depth):
    return F.l1_loss(predicted_depth, gt_depth)