import warnings
import os
import re

from skimage import io
from skimage.color import rgb2gray
from skimage.morphology import medial_axis, skeletonize
from scipy.ndimage.morphology import distance_transform_edt

import functions
import numpy as np
import scipy.io as sio
from visualization import VisualScene


class ImageProcessor:
    """
    Reads in a scene file and outputs a skeleton, the feature transform,
    distance transform or the medial axis. Stores the images to file if requested.
    """
    file_postfix = '.eps'

    skeleton_folder = 'skeletons'
    feature_transform_folder = 'feature_transforms'
    medial_axis_folder = 'medial_axes'

    @staticmethod
    def get_skeleton(scene, store=True):
        """
        Computes the skeleton of the scene. Returns an image with black values on skeleton points.
        :param scene: scene with obstacles.
        :param store: Write skeleton to file
        :return: 2D numpy array of pixels. Orientation is different from matplotlib/tkinter indexing!
        """
        if not os.path.isdir(ImageProcessor.skeleton_folder):
            os.makedirs(ImageProcessor.skeleton_folder)
        obstacle_file = scene.config['general']['obstacle_file']
        skeleton_file = ImageProcessor.skeleton_folder \
                        + re.search('/[^/\.]+', obstacle_file).group(0) + ImageProcessor.file_postfix
        if not os.path.exists(skeleton_file):
            functions.log("No corresponding skeleton found, creating from obstacle file")
            dummy_vis = EmptyVisualization(scene, filename=skeleton_file)
            dummy_vis.step_callback = dummy_vis.loop
            dummy_vis.start()
            data = io.imread(skeleton_file)
            gray_data = rgb2gray(data)
            skeleton = 1 - skeletonize(gray_data)
            if store:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    io.imsave(skeleton_file, skeleton.astype(float))
        else:
            functions.log("Skeleton found, loading from file")
            data = io.imread(skeleton_file)
            skeleton = rgb2gray(data)
        return skeleton

    @staticmethod
    def get_medial_axis(scene, store=True):
        """
        Extracts the medial axis of the scene. Returns an image with black values on medial axis points.
        :param scene: scene with obstacles.
        :param store: Write medial axis to file
        :return: 2D numpy array of pixels. Orientation is different from matplotlib/tkinter indexing!
        """
        if not os.path.isdir(ImageProcessor.medial_axis_folder):
            os.makedirs(ImageProcessor.medial_axis_folder)
        obstacle_file = scene.config['general']['obstacle_file']
        medial_axis_file = ImageProcessor.medial_axis_folder \
                           + re.search('/[^/\.]+', obstacle_file).group(0) + ImageProcessor.file_postfix
        if not os.path.exists(medial_axis_file):
            functions.log("No corresponding medial axis found, creating from obstacle file")
            dummy_vis = EmptyVisualization(scene, filename=medial_axis_file)
            dummy_vis.step_callback = dummy_vis.loop
            dummy_vis.start()
            data = io.imread(medial_axis_file)
            gray_data = rgb2gray(data)
            gray_data[0, :] = gray_data[-1, :] = gray_data[:, 0] = gray_data[:, -1] = 0
            exit_dims = [0.4, 0.6]
            # If I start using it, read the exit from the JSON file.
            # In that case, fix the corners
            width = gray_data.shape[1]
            height = gray_data.shape[0]
            gray_data[-1, exit_dims[0] * width:exit_dims[1] * width] = 1
            gray_data[exit_dims[0] * height:exit_dims[1] * height, 0] = 1
            medial = 1 - medial_axis(gray_data)

            if store:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    io.imsave(medial_axis_file, medial.astype(float))
        else:
            functions.log("Medial axis found, loading from file")
            data = io.imread(medial_axis_file)
            medial = rgb2gray(data)
        return medial

    @staticmethod
    def get_feature_transform(scene, get_distance_transform=False, store=True):
        """
        Computes the feature and distance transform of the scene.
        For the feature transform, an 2D numpy array of pixels is returned with of each pixel the nearest boundary
        For the distance transform, an 2D numpy array of pixels is returned
        with of each pixel the distance to the boundary
        :param scene: scene with obstacles.
        :param get_distance_transform If true, return a tuple with second argument the distance transform
        :param store: Write skeleton to file
        :return: 2D numpy array of pixels. Orientation is different from matplotlib/tkinter indexing!
        """
        if not os.path.isdir(ImageProcessor.feature_transform_folder):
            os.makedirs(ImageProcessor.feature_transform_folder)
        obstacle_file = scene.config['general']['obstacle_file']
        feature_file = ImageProcessor.feature_transform_folder \
                       + re.search('/[^/\.]+', obstacle_file).group(0) + ImageProcessor.file_postfix
        feature_matrix_file = feature_file.replace(ImageProcessor.file_postfix, '.mat')  # Remove for clear restart
        if not os.path.exists(feature_matrix_file):
            functions.log("No corresponding feature transform found, creating from obstacle file")
            dummy_vis = EmptyVisualization(scene, filename=feature_file)
            dummy_vis.step_callback = dummy_vis.loop
            dummy_vis.start()
            data = io.imread(feature_file)
            print("Read in data before feature transform", data.shape)
            gray_data = rgb2gray(data)
            gray_data[0, :] = gray_data[-1, :] = gray_data[:, 0] = gray_data[:, -1] = 0
            distance_transform, feature_transform = distance_transform_edt(gray_data, return_indices=True)
            if store:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    sio.savemat(feature_matrix_file, {'feature_transform': feature_transform,
                                                      'distance_transform': distance_transform})
                    io.imsave(feature_file, (distance_transform / np.max(distance_transform)).astype(float))
        else:
            functions.log("Feature transform found, loading from file")
            data = sio.loadmat(feature_matrix_file)
            feature_transform = data['feature_transform']
            distance_transform = data['distance_transform']
        if get_distance_transform:
            return feature_transform, distance_transform
        else:
            return feature_transform


class EmptyVisualization(VisualScene):
    """
    Adaption of screen visualizer to extract eps image from scene
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.filename = kwargs['filename']
        self.drawn = 2
        self.delay = 400
        scale = self.scene.config['skeleton'].getfloat('pixel_scale')
        self.size = self.scene.size * scale

    def draw_scene(self):
        if self.drawn:  # Pretty bad, but I blame Tkinter
            self.drawn -= 1
            self.canvas.delete('all')
            for obstacle in self.scene.obstacle_list:
                if not obstacle.accessible:
                    self.draw_obstacle(obstacle)
        else:
            self.store_scene(None, self.filename)
            print(self.filename)
            print("Scene size", self.size)
            self.window.destroy()

if __name__=="__main__":
    from simulation_manager import SimulationManager
    from scene import Scene
    config = SimulationManager.get_default_config()
    scene = Scene(config)
    ImageProcessor.get_feature_transform(scene)
    ImageProcessor.get_medial_axis(scene)
    ImageProcessor.get_skeleton(scene)
