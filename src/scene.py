__author__ = 'omar'

import random
import pickle
import itertools

from functions import *
from pedestrian import Pedestrian, EmptyPedestrian
from geometry import Point, Size, LineSegment
import visualization as vis


class Scene:
    """
    Models a scene. A scene is a rectangular object with obstacles and pedestrians inside.
    """

    def __init__(self, size: Size, pedestrian_number, obstacle_file, mde=True, dt=0.05, cache='read'):
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
        self.time = 0
        self.obstacle_list = []
        self.on_step_functions = []
        self.on_pedestrian_exit_functions = []
        self.on_finish_functions = []

        self._read_json_file(file_name=obstacle_file)
        self.position_array = np.zeros([self.pedestrian_number, 2])
        self.last_position_array = np.zeros([self.pedestrian_number, 2])
        self.velocity_array = np.zeros([self.pedestrian_number, 2])
        self.pedestrian_cells = np.zeros([self.pedestrian_number, 2])
        self.alive_array = np.ones(self.pedestrian_number)
        self.cell_dict = {}
        self.minimal_distance = 0.7
        self.number_of_cells = (20, 20)
        self.cell_size = Size(self.size.array / self.number_of_cells)
        self.mde = mde  # Minimum Distance Enforcement
        if cache == 'read':
            self._load_cells()
        else:
            self._create_cells()
        if cache == 'write':
            self._store_cells()
        self.pedestrian_size = Size([0.4, 0.4])
        self.pedestrian_list = []
        self._init_pedestrians()
        self.status = 'RUNNING'

    def _init_pedestrians(self):
        self.pedestrian_list = [
            Pedestrian(self, counter, self.exit_obs, color=random.choice(vis.VisualScene.color_list))
            for counter in range(self.pedestrian_number)]
        self._fill_cells()

    def set_on_step_functions(self, *on_step):
        """
        Adds functions to list called on each time step.
        :param on_step: functions (without arguments)
        :return: None
        """
        self.on_step_functions += on_step

    def set_on_pedestrian_exit_functions(self, *on_pedestrian_exit):
        """
        Adds functions to list called each time a pedestrian exits.
        :param on_pedestrian_exit: functions which take Pedestrian as argument
        :return: None
        """
        self.on_pedestrian_exit_functions += on_pedestrian_exit

    def set_on_finish_functions(self, *on_finish):
        """
        Adds functions to list called on simulation finish.
        :param on_finish: functions (without arguments)
        :return: None
        """
        self.on_finish_functions += on_finish

    def _read_json_file(self, file_name: str):
        """
        Reads in a JSON file and stores the obstacle data in the scene.
        The file must consist of one JSON object with keys 'obstacles', 'exits', and 'entrances'
        Every key must have a list of instances, each having a 'name', a 'begin' and a 'size'.
        Note that sizes are fractions of the scene size. A size of 0 is converted to 1 size unit.
        :param file_name: file name string of the JSON file
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
        if len(data['exits']) == 0:
            raise AttributeError('No exits specified in %s' % file_name)
        elif len(data['exits']) > 1:
            raise NotImplementedError('Multiple exits specified in %s' % file_name)
        for exit_data in data['exits']:
            begin = Point(self.size * exit_data['begin'])
            size = self.size.array * np.array(exit_data['size'])
            name = exit_data["name"]

            for dim in range(2):
                if size[dim] == 0.:
                    size[dim] = 1.

            self.exit_obs = Exit(begin, Size(size), name)
            self.obstacle_list.append(self.exit_obs)

    def _create_cells(self):
        """
        Creates the cell objects into which the scene is partitioned.
        The cell objects are stored in the scenes cell_dict as {(row, column): Cell}
        This is a time intensive operation which can be avoided by using the cache function
        :return: None
        """
        fyi("Started preprocessing cells")
        self.cell_dict = {}
        row_number, col_number = self.number_of_cells
        for row in range(row_number):
            for col in range(col_number):
                start = Point(self.cell_size.array * [row, col])
                cell = Cell(row, col, start, self.cell_size)
                self.cell_dict[(row, col)] = cell
        for cell_location in self.cell_dict:
            self.cell_dict[cell_location].obtain_relevant_obstacles(self.obstacle_list)
        fyi("Finished preprocessing cells")

    def _fill_cells(self):
        """
        This method fills the cells in self.cell_dict with the pedestrians
        :return: None
        """
        cell_locations = np.floor(self.position_array / self.cell_size)
        self.pedestrian_cells = cell_locations
        for index in range(self.pedestrian_number):
            cell_location = (int(cell_locations[index, 0]), int(cell_locations[index, 1]))
            self.cell_dict[cell_location].add_pedestrian(self.pedestrian_list[index])

    def _store_cells(self, filename='cells.bin'):
        """
        This method pickles the cells dictionary (without pedestrians) into a file.
        It can be loaded using _load_cells
        :param filename: name of pickled scene file
        :return: None
        """
        with open(filename, 'wb') as pickle_file:
            pickle.dump(self.cell_dict, pickle_file)

    def _load_cells(self, filename='cells.bin'):
        """
        Opens and unpickles the file containing the scene dictionary
        If file does not exist, creates new cells.
        If cells do not correspond to the scene + obstacles, creates new cells.
        :param filename: name of pickled scene file
        :return: None
        """
        fyi("Loading cell objects from file")

        def reject_cells():
            fyi("Cells cache does not correspond to this scene. Creating new cells and storing those.")
            self._create_cells()
            self._store_cells()

        import os.path
        if os.path.isfile(filename):
            with open(filename, 'rb') as pickle_file:
                self.cell_dict = pickle.load(pickle_file)
        else:
            reject_cells()
        if not self._validate_cells():
            reject_cells()

    def _validate_cells(self):
        """
        Compares the cell dictionary to the scene information.
        Polls a cells and checks its location and its size to see if it behaves as expected.
        :return: False if the method detects an inconsistency, True otherwise
        """
        cell_location = set(self.cell_dict).pop()
        correct_index = all([cell_location[dim] < self.number_of_cells[dim] for dim in range(2)])
        correct_size = all((self.cell_dict[cell_location].size - self.cell_size).array == 0)
        correct_obstacle = {obs.name for obs in self.obstacle_list} \
                           == {obs.name for cell in self.cell_dict.values() for obs in cell.obstacle_set}
        return correct_index and correct_size and correct_obstacle

    def get_cell_from_position(self, position):
        """
        Obtain the cell corresponding to a certain position
        :param position: position
        :return: corresponding cell
        """
        size = Size(self.size.array / self.number_of_cells)
        cell_location = np.floor(np.array(position) / size)
        return self.cell_dict[(int(cell_location[0]), int(cell_location[1]))]

    def get_pedestrian_cells(self):
        """
        Obtain the pedestrian distribution over the cells.
        :return:array with integer values per pedestrian corresponding to its cell.
        """
        raw_cell_locations = np.floor(self.position_array / self.cell_size)
        return raw_cell_locations

    def get_stationary_pedestrians(self):
        pos_difference = np.linalg.norm(self.position_array - self.last_position_array, axis=1)
        not_moved = pos_difference == 0
        # is_alive = np.array(self.alive_array,dtype=bool) # Not necessary, we check in planner anyway
        # combined_stationary_information = np.hstack([not_moved[:,None],is_alive[:,None]])
        return not_moved

    def update_cells(self):
        """
        Update all the pedestrians, but by looking per cell what the new situation is.
        :return: None
        """
        new_ped_cells = self.get_pedestrian_cells()
        needs_update = self.pedestrian_cells != new_ped_cells
        for index in range(self.pedestrian_number):
            if self.alive_array[index]:
                if any(needs_update[index]):
                    pedestrian = self.pedestrian_list[index]
                    cell = pedestrian.cell
                    new_cell_orientation = (int(new_ped_cells[index, 0]), int(new_ped_cells[index, 1]))
                    if new_cell_orientation in self.cell_dict:
                        cell.remove_pedestrian(self.pedestrian_list[index])
                        new_cell = self.cell_dict[new_cell_orientation]
                        new_cell.add_pedestrian(pedestrian)
                    else:
                        pass
        self.pedestrian_cells = new_ped_cells

    def _minimum_distance_enforcement(self, min_distance):
        """
        Finds the pedestrian pairs that are closer than the specified distance.
        Does so by comparing the distances of all pedestrians a,b in a cell.
        Note that intercellullar pedestrian pairs are ignored,
        we might fix this later.

        :param min_distance: minimum distance between pedestrians, including their size.
        :return: list of pedestrian index pairs with distances lower than min_distance.
        """
        list_a = []
        list_b = []
        index_list = []
        for cell in self.cell_dict.values():
            for comb in itertools.combinations(cell.pedestrian_set, 2):
                list_a.append(comb[0].position.array)
                list_b.append(comb[1].position.array)
                index_list.append([comb[0].counter, comb[1].counter])
        array_a = np.array(list_a)
        array_b = np.array(list_b)
        array_index = np.array(index_list)
        differences = array_a - array_b
        if len(differences) == 0:
            return
        distances = np.linalg.norm(differences, axis=1)
        indices = np.where(distances < min_distance)[0]

        mde_pairs = array_index[indices]
        # Todo: Change perturbation to eps
        mde_corrections = (min_distance / (distances[indices][:, None] + 0.001) - 1) * differences[indices] / 2
        ordered_corrections = np.zeros([self.pedestrian_number, 2])
        for it in range(len(mde_pairs)):
            pair = mde_pairs[it]
            ped_a = self.pedestrian_list[pair[0]]
            ped_b = self.pedestrian_list[pair[1]]
            ordered_corrections[ped_a.counter] += mde_corrections[it]
            ordered_corrections[ped_b.counter] -= mde_corrections[it]
        self.position_array += ordered_corrections

    def remove_pedestrian(self, pedestrian):
        """
        Removes a pedestrian from the scene by replacing it with an empty pedestrian
        The replace is required so that the indexing is not disturbed.
        :param pedestrian: The pedestrian instance to be removed.
        :return: None
        """
        # assert pedestrian.is_done()
        assert self.pedestrian_list[pedestrian.counter] == pedestrian
        pedestrian.cell.remove_pedestrian(pedestrian)
        counter = pedestrian.counter
        empty_ped = EmptyPedestrian(self, counter)
        self.pedestrian_list[counter] = empty_ped
        self.alive_array[counter] = 0
        for function in self.on_pedestrian_exit_functions:
            function(pedestrian)
        if np.sum(self.alive_array) == 0:
            self.status = 'DONE'

    def is_within_boundaries(self, coord: Point) -> bool:
        within_boundaries = all(np.array([0, 0]) < coord.array) and all(coord.array < self.size.array)
        return within_boundaries

    def is_accessible(self, coord: Point, at_start=False) -> bool:
        """
        Checking whether the coordinate present is an accessible coordinate on the scene.
        When evaluated at the start, the exit is not an accessible object. That would be weird. We can eliminate this later though.
        :param coord: Coordinates to be checked
        :param at_start: Whether to be evaluated at the start
        :return: True if accessible, False otherwise.
        """
        if not self.is_within_boundaries(coord):
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
        self.time += self.dt
        self.last_position_array = np.array(self.position_array)
        self.position_array += self.velocity_array * self.dt
        if self.mde:
            self._minimum_distance_enforcement(self.minimal_distance)
        self.update_cells()

    def finish(self):
        """
        :return: None
        """
        [on_finish() for on_finish in self.on_finish_functions]
        fyi('Simulation is finished. Exiting')


class Cell:
    """
    Models a cell from the partitioned scene.
    This is to accommodate the UIC computations as well as to perform a more efficient scene evaluation.
    We assume equal sized grid cells.
    """

    def __init__(self, row: int, column: int, begin: Point, size: Size):
        self.location = (row, column)
        self.begin = begin
        self.size = size
        self.center = self.begin + self.size * 0.5
        self.pedestrian_set = set()
        self.obstacle_set = set()

    def obtain_relevant_obstacles(self, obstacle_list):
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
        corner_points[2], corner_points[3] = corner_points[3], corner_points[2]
        # Create edges
        edge_list = []
        for i in range(4):
            edge_list.append(LineSegment([corner_points[i], corner_points[i - 1]]))
            # Check edges for every obstacle
        for obstacle in obstacle_list:
            for edge in edge_list:
                if edge.crosses_obstacle(obstacle):
                    self.obstacle_set.add(obstacle)
                    break

    def add_pedestrian(self, pedestrian):
        assert pedestrian not in self.pedestrian_set
        pedestrian.cell = self
        self.pedestrian_set.add(pedestrian)

    def remove_pedestrian(self, pedestrian):
        assert pedestrian in self.pedestrian_set
        self.pedestrian_set.remove(pedestrian)

    def is_accessible(self, coord, at_start=False):
        within_cell_boundaries = all(self.begin.array < coord.array) and all(
            coord.array < self.begin.array + self.size.array)
        if not within_cell_boundaries:
            warn('Accessibility of %s requested outside of %s' % (coord, self))
            return False
        if at_start:
            return all([coord not in obstacle for obstacle in self.obstacle_set])
        else:
            return all([coord not in obstacle or obstacle.permeable for obstacle in self.obstacle_set])

    def __contains__(self, coord):
        return all([self.begin[dim] <= coord[dim] <= self.begin[dim] + self.size[dim] for dim in range(2)])

    def __repr__(self):
        return "Cell %s from %s to %s" % (self.location, self.begin, self.begin + self.size)

    def __str__(self):
        return "Cell %s. Begin: %s. End %s\nPedestrians: %s\nObstacles: %s" % (
            self.location, self.begin, self.begin + self.size, self.pedestrian_set, self.obstacle_set
        )


class Obstacle:
    """
    Models an rectangular obstacle within the domain. The obstacle has a starting point, a size,
    and a permeability factor.
    """

    def __init__(self, begin: Point, size: Size, name: str, permeable=False):
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
        self.margin_list = [Point(np.sign([x - 0.5, y - 0.5])) for x in range(2) for y in range(2)]
        self.in_interior = True
        self.center = self.begin + self.size * 0.5

    def __contains__(self, coord: Point):
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

    def __init__(self, begin: Point, size: Size, name: str, spawn_rate=0):
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