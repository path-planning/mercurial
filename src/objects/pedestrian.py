import numpy as np

from math_objects import functions as ft
from math_objects.geometry import Point, Velocity

class Pedestrian(object):
    """
    Class for modeling a pedestrian. Apart from physical properties like position and velocity,
    this class also contains agent properties like planned path, (NYI:) goal, social forces,
    and maximum speed.
    """

    def __init__(self, scene, counter, goals, position=Point([0, 0]), index=-1):
        """
        Initializes the pedestrian
        :param scene: Scene instance for the pedestrian to walk in
        :param counter: number of the pedestrian in the scene list. Not relied upon currently
        :param goal: Goal obstacle (Exit instance)
        :param position: Current position of the pedestrian. Position [0,0] will create a randomized position
        :param color: Color the pedestrian should be drawn with. Currently random, can be changed to
        observe effect of social forces.
        :return: Pedestrian instance
        """
        self.scene = scene
        self.counter = counter
        if index < 0:
            self.index = counter
        else:
            self.index = index
        self.position = position
        self.color = self._convert_speed_to_color()
        self.goals = goals
        while self.position.is_zero() and type(self) == Pedestrian:
            new_position = scene.size.random_internal_point()
            if scene.is_accessible(new_position, at_start=True):
                self.position = new_position
        self.origin = self.position

    def __str__(self):
        """
        String representation for pedestrian having position, angle,
        and whether or not pedestrian is still in the scene
        :return: string representation
        """
        return "Pedestrian %d (index %d) \tPosition: %s\tAngle %.2f pi" % \
               (self.counter, self.index, self.position, self.velocity.angle / np.pi)

    def __repr__(self):
        """
        :return: Unique string identifier using counter integer
        """
        return "Pedestrian#%d (%d)" % (self.counter, self.index)

    def _convert_speed_to_color(self):
        """
        Computes a color between red and blue based on pedestrian max velocity.
        Red is fast, blue is slow.
        :return: tkinter RGB code for color
        """
        start = np.min(self.scene.max_speed_array)
        end = np.max(self.scene.max_speed_array)
        if start == end:
            return 'blue'
        max_val = 255
        speed = self.scene.max_speed_array[self.index]
        red = int(max_val * (speed - start) / (end - start))
        green = 0
        blue = int(max_val * (speed - end) / (start - end))
        return "#%02x%02x%02x" % (red, green, blue)


    def move_to_position(self, position: Point, dt):
        """
        Higher level updating of the pedestrian. Checks whether the position is reachable this time step.
        If so, moves to that position. Directly attaining the position within the current radius enables us
        to be less numerically accurate with the velocity directing to the goal.
        :param position: Position that should be attained
        :param dt: time step
        :return: True when position is attained, false otherwise
        """
        distance = position - self.position
        if ft.norm(distance.array[0], distance.array[1]) < self.scene.max_speed_array[self.index] * dt:
            # should be enough to avoid small numerical error
            if self.scene.is_accessible(position):
                self.position = position
        return False

    @property
    def velocity(self):
        """
        Velocity getter
        :return:
        """
        return Velocity(self.scene.velocity_array[self.index])

    @velocity.setter
    def velocity(self, value):
        """
        Sets velocity value and automatically rescales it to maximum speed.
        This is an assumption that can be dropped when we implement the UIC
        :param value: 2D velocity with the correct direction
        :return: None
        """
        self._velocity = value
        if value:
            self._velocity.rescale(self.scene.max_speed_array[self.index])
            self.scene.velocity_array[self.index] = self._velocity.array

    @property
    def position(self):
        """
        Position getter
        :return: Current position
        """
        return Point(self.scene.position_array[self.index])

    @position.setter
    def position(self, point):
        """
        Position setter. Eases checks and debugging.
        Note that setting a point this way does not update the scene position array.
        Use manual_move() for that.
        :param point: New position
        :return: None
        """
        self.scene.position_array[self.index] = point.array