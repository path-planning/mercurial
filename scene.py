__author__ = 'omar'

import random

from functions import *
from pedestrian import Pedestrian
from geometry import Point, Size
import visualization as vis


class Scene:
    """
    Models a scene. A scene is a rectangular object with obstacles and pedestrians inside.
    """
    def __init__(self, size: Size, pedestrian_number, obstacle_file,dt=0.05):
        """
        Initializes a Scene
        :param size: Size object holding the size values of the scene
        :param pedestrian_number: Number of pedestrians on initialization in the scene
        :param obstacle_file: name of the file containing the obstacles.
        :param dt: update time step
        :return: scene instance.
        """
        self.size = size
        self.ped_number = pedestrian_number
        self.dt = dt
        self.obs_list = []
        self._read_json_file(file_name=obstacle_file)
        self.ped_list = [Pedestrian(self, i, self.exit_obs, color=random.choice(vis.VisualScene.color_list)) for i in
                         range(pedestrian_number)]

    def _read_json_file(self,file_name: str):
        """
        Reads in a JSON file and stores the obstacle data in the scene.
        The file must consist of one JSON object with keys 'obstacles', 'exits', and 'entrances'
        Every key must have a list of instances, each having a 'name', a 'begin' and a 'size'.
        Note that sizes are fractions of the scene size. A size of 0 is converted to 1 pixel.
        :param file_name: String leading to the JSON file
        :return: None
        """
        import json
        with open(file_name,'r') as json_file:
            data = json.loads(json_file.read())
        for obstacle_data in data["obstacles"]:
            begin = Point(self.size*obstacle_data['begin'])
            size = Size(self.size*obstacle_data['size'])
            name = obstacle_data["name"]
            self.obs_list.append(Obstacle(begin,size,name))
        for exit_data in data['exits']:
            begin = Point(self.size*exit_data['begin'])
            size = self.size.array*np.array(exit_data['size'])
            name = exit_data["name"]

            for dim in range(2):
                if size[dim] == 0.:
                    size[dim] = 1.

            self.exit_obs = Exit(begin,Size(size),name)
            self.obs_list.append(self.exit_obs)


    def is_accessible(self, coord: Point, at_start=False) -> bool:
        """
        Checking whether the coordinate present is an accessible coordinate on the scene.
        When evaluated at the start, the exit is not an accessible object. That would be weird. We can eliminate this later though.
        :param coord: Coordinates to be checked
        :param at_start: Whether to be evaluated at the start
        :return: True if accessible, False otherwise.
        """
        within_boundaries = all(np.array([0, 0]) < coord.array) and all(coord.array < self.size.array)
        if not within_boundaries:
            return False
        if at_start:
            return all([coord not in obstacle for obstacle in self.obs_list])
        else:
            return all([coord not in obstacle or obstacle.permeable for obstacle in self.obs_list])

    def evaluate_pedestrians(self):
        for pedestrian in self.ped_list:
            pedestrian.update_position(self.dt)


class Obstacle:
    """
    Models an rectangular obstacle within the domain. The obstacle has a starting point, a size,
    and a permeability factor.
    """
    def __init__(self, begin: Point, size:Size, name:str, permeable=False):
        """
        Constructor for the obstacle.
        :param begin: Point object with lowerleft values of object
        :param size: Size object with size values of object
        :param name: name (id) for object
        :param permeable: whether pedestrians are able to go through the object
        :return: object instance.
        """
        self.begin = begin
        self.size = size
        self.end = self.begin + self.size
        self.name = name
        self.permeable = permeable
        self.color = 'black'
        self.corner_info_list = [(Point(self.begin + Size([x, y]) * self.size), [x, y]) for x in range(2) for y in
                                 range(2)]
        self.corner_list = [Point(self.begin + Size([x, y]) * self.size) for x in range(2) for y in range(2)]
        # Safety margin for around the obstacle corners.
        self.margin_list = [Point(np.sign([x - 0.5, y - 0.5])) * 3 for x in range(2) for y in range(2)]
        self.in_interior = True
        self.center = self.begin + self.size * 0.5

    def __contains__(self, coord:Point):
        return all([self.begin[dim] <= coord[dim] <= self.begin[dim] + self.size[dim] for dim in range(2)])

    def __getitem__(self, item):
        return [self.begin, self.end][item]

    def __repr__(self):
        return "Instance: %s '%s'" % (self.__class__.__name__, self.name)

    def __str__(self):
        return "Obstacle %s. Bottom left: %s, Top right: %s" % (self.name, self.begin, self.end)


class Entrance(Obstacle):
    """
    Not yet implemented
    """
    def __init__(self, begin:Point, size:Size, name:str, spawn_rate=0):
        Obstacle.__init__(self, begin, size, name)
        self.spawn_rate = spawn_rate
        self.color = 'blue'


class Exit(Obstacle):
    """
    Model an exit obstacle. This is, unlike other obstacles, permeable and has no dodge margin.
    """
    def __init__(self, begin, size, name):
        super(Exit,self).__init__( begin, size, name, permeable=True)
        self.color = 'red'
        self.in_interior = False
        self.margin_list = [Point(np.zeros(2)) for _ in range(4)]
