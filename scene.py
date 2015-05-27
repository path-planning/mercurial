__author__ = 'omar'

import random

from functions import *
from pedestrian import Pedestrian, EmptyPedestrian
from geometry import Point, Size, LineSegment
import visualization as vis


class Scene:
    """
    Models a scene. A scene is a rectangular object with obstacles and pedestrians inside.
    """

    def __init__(self, size: Size, pedestrian_number, obstacle_file, dt=0.05):
        """
        Initializes a Scene
        :param size: Size object holding the size values of the scene
        :param pedestrian_number: Number of pedestrians on initialization in the scene
        :param obstacle_file: name of the file containing the obstacles.
        :param dt: update time step
        :return: scene instance.
        """
        self.size = size
        self.pedestrian_number = pedestrian_number
        self.dt = dt
        self.obstacle_list = []
        self._read_json_file(file_name=obstacle_file)
        self.position_array = np.zeros([self.pedestrian_number, 2])
        self.velocity_array = np.zeros([self.pedestrian_number, 2])
        self.pedestrian_list = [Pedestrian(self, i, self.exit_obs, color=random.choice(vis.VisualScene.color_list)) for
                                i in
                                range(pedestrian_number)]
        self.cell_dict = {}
        self.number_of_cells = (40, 40)
        self._create_cells()
        self._fill_cells()

    def _create_cells(self):
        row_number, col_number = self.number_of_cells
        size = Size(self.size.array / self.number_of_cells)
        for row in range(row_number):
            for col in range(col_number):
                start = Point(size.array * [row, col])
                cell = Cell(row, col, start, size)
                self.cell_dict[(row, col)] = cell

    def _fill_cells(self):
        fyi("Started preprocessing cells")
        size = Size(self.size.array / self.number_of_cells)
        cell_locations = np.floor(self.position_array / size)
        for index in range(self.pedestrian_number):
            cell_location = (int(cell_locations[index, 0]), int(cell_locations[index, 1]))
            self.cell_dict[cell_location].add_pedestrian(self.pedestrian_list[index])
        for cell_location in self.cell_dict:
            self.cell_dict[cell_location].obtain_relevant_obstacles(self.obstacle_list)
            ped_set = self.cell_dict[cell_location].pedestrian_set
            obstacle_set = self.cell_dict[cell_location].obstacle_set
        fyi("Finished preprocessing cells")

    def get_cell_from_position(self,position):
        size = Size(self.size.array / self.number_of_cells)
        cell_location = np.floor(np.array(position) / size)
        return self.cell_dict[(int(cell_location[0]),int(cell_location[1]))]

    def _read_json_file(self, file_name: str):
        """
        Reads in a JSON file and stores the obstacle data in the scene.
        The file must consist of one JSON object with keys 'obstacles', 'exits', and 'entrances'
        Every key must have a list of instances, each having a 'name', a 'begin' and a 'size'.
        Note that sizes are fractions of the scene size. A size of 0 is converted to 1 size unit.
        :param file_name: String leading to the JSON file
        :return: None
        """
        import json

        with open(file_name, 'r') as json_file:
            data = json.loads(json_file.read())
        for obstacle_data in data["obstacles"]:
            begin = Point(self.size * obstacle_data['begin'])
            size = Size(self.size * obstacle_data['size'])
            name = obstacle_data["name"]
            self.obstacle_list.append(Obstacle(begin, size, name))
        for exit_data in data['exits']:
            begin = Point(self.size * exit_data['begin'])
            size = self.size.array * np.array(exit_data['size'])
            name = exit_data["name"]

            for dim in range(2):
                if size[dim] == 0.:
                    size[dim] = 1.

            self.exit_obs = Exit(begin, Size(size), name)
            self.obstacle_list.append(self.exit_obs)

    def remove_pedestrian(self, pedestrian):
        """
        Removes a pedestrian from the scene by replacing it with an empty pedestrian
        The replace is required so that the indexing is not disturbed.
        :param pedestrian: The pedestrian instance to be removed.
        :return: None
        """
        # assert pedestrian.is_done()
        assert self.pedestrian_list[pedestrian.counter] == pedestrian
        counter = pedestrian.counter
        empty_ped = EmptyPedestrian(self, counter)
        self.pedestrian_list[counter] = empty_ped

    def get_global_accesibility(self, at_start=False):
        # Todo: Vectorize this operation
        # Within boundaries is easily vectorized.
        # In order to vectorize the obstacle method, we need more magic.
        pass

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
            return all([coord not in obstacle for obstacle in self.obstacle_list])
        else:
            return all([coord not in obstacle or obstacle.permeable for obstacle in self.obstacle_list])

    def move_pedestrians(self):
        """
        Performs a vectorized move of all the pedestrians.
        Assumes that all the velocities have been set accordingly.
        :return: None
        """

        self.position_array += self.velocity_array * self.dt


class Cell:
    """
    Models a cell from the partitioned scene.
    Currently, this is meant for applying the UIC.
    In the future, we like to refactor the scene accessibility in here as well.
    We assume equal sized cells.
    """

    def __init__(self, row: int, column: int, begin: Point, size: Size):
        self.location = (row, column)
        self.begin = begin
        self.size = size
        self.center = self.begin+self.size*0.5
        self.pedestrian_set = set()
        self.obstacle_set = set()

    def obtain_relevant_obstacles(self,obstacle_list):
        # Check if obstacle is contained in cell, or cell contained in obstacle
        for obstacle in obstacle_list:
            if obstacle.center in self or self.center in obstacle:
                # Possible optimization:
                # If cells completely lie within obstacles, make them moot.
                self.obstacle_set.add(obstacle)
        # Check if any of the cell lines crosses an obstacle
            # Create corners
        corner_points = [(Point(self.begin + Size([x, y]) * self.size)) for x in range(2) for y in
                                 range(2)]
        corner_points[2],corner_points[3] = corner_points[3],corner_points[2]
            # Create edges
        edge_list = []
        for i in range(4):
            edge_list.append(LineSegment([corner_points[i],corner_points[i-1]]))
            # Check edges for every obstacle
        for obstacle in obstacle_list:
            for edge in edge_list:
                if edge.crosses_obstacle(obstacle):
                    self.obstacle_set.add(obstacle)
                    break



    def add_pedestrian(self, pedestrian):
        assert pedestrian not in self.pedestrian_set
        self.pedestrian_set.add(pedestrian)

    def remove_pedestrian(self, pedestrian):
        assert pedestrian in self.pedestrian_set
        self.pedestrian_set.remove(pedestrian)

    def __contains__(self, coord):
        return all([self.begin[dim] <= coord[dim] <= self.begin[dim] + self.size[dim] for dim in range(2)])

    def __repr__(self):
        return "Cell %s from %s to %s" % (self.location, self.begin, self.begin + self.size)

    def __str__(self):
        return "Cell %s. Begin: %s. End %s\nPedestrians: %s\nObstacles: %s"%(
            self.location,self.begin,self.begin+self.size,self.pedestrian_set,self.obstacle_set
        )

class Obstacle:
    """
    Models an rectangular obstacle within the domain. The obstacle has a starting point, a size,
    and a permeability factor.
    """

    def __init__(self, begin: Point, size:Size, name:str, permeable=False):
        """
        Constructor for the obstacle.
        :param begin: Point object with lower-left values of object
        :param size: Size object with size values of object
        :param name: name (id) for object
        :param permeable: whether pedestrians are able to go through this object
        :return: object instance.
        """
        self.begin = begin
        self.size = size
        self.end = self.begin + self.size
        self.name = name
        self.permeable = permeable
        self.color = 'black'
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
        return "%s#%s" % (self.__class__.__name__, self.name)

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
        super(Exit, self).__init__(begin, size, name, permeable=True)
        self.color = 'red'
        self.in_interior = False
        self.margin_list = [Point(np.zeros(2)) for _ in range(4)]

#
# scene = Scene(size=Size([400, 500]), obstacle_file="demo_obstacle_list.json",
#               pedestrian_number=100)