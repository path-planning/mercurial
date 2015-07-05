__author__ = 'omar'

import networkx as nx

from functions import *
from geometry import LineSegment, Path, Point, Coordinate, Interval, Velocity
from pedestrian import Pedestrian
from scene import Obstacle

class Planner:
    on_track = 0
    reached_checkpoint = 1
    other_state = 2

    def __init__(self, scene):
        self.scene = scene
        for pedestrian in self.scene.pedestrian_list:
            pedestrian.path = self.create_path(pedestrian, self.scene.exit_obs)
            pedestrian.line = pedestrian.path.pop_next_segment()
            # pedestrian.velocity = Velocity(pedestrian.line.end - pedestrian.position.array)

    def create_path(self, pedestrian: Pedestrian, goal_obstacle) -> Path:
        path_to_exit = Path([])
        sub_start = pedestrian.position
        while not (sub_start in goal_obstacle):
            goal = Planner.get_goal(sub_start, goal_obstacle)
            line_to_goal = LineSegment([sub_start, goal])
            angle_to_goal = (goal - sub_start).angle
            colliding_obstacles = []
            for obstacle in self.scene.obstacle_list:
                if obstacle.in_interior and line_to_goal.crosses_obstacle(obstacle):
                    colliding_obstacles.append(obstacle)
            if colliding_obstacles:
                sub_finish = self.get_intermediate_goal(sub_start, angle_to_goal, colliding_obstacles)
            else:
                sub_finish = goal
            path_to_exit.append(LineSegment([sub_start, sub_finish]))
            sub_start = sub_finish
        return path_to_exit

    @staticmethod
    def get_goal(position, obstacle):
        # Checking whether the x or y component already lies between the bounds of object.
        # Otherwise, desired component is the closest corner.
        goal_dim = [0, 0]
        for dim in range(2):
            obs_interval = Interval([obstacle.begin[dim], obstacle.end[dim]])
            pos_dim = position[dim]
            if pos_dim in obs_interval:
                goal_dim[dim] = position[dim]
            elif pos_dim < obs_interval.begin:
                goal_dim[dim] = obs_interval.begin
            else:
                goal_dim[dim] = obs_interval.end
        return Point(goal_dim)

    @staticmethod
    def get_intermediate_goal(start, angle_to_goal, obstacles, safe_distance=3.):
        # In this method, 0 == False == Left, 1 == True == Right
        corner_points = [None, None]  # max corners left and right from destination
        max_angles = [0, 0]
        for obstacle in obstacles:
            for corner, corner_location in obstacle.corner_info_list:
                angle_to_corner = (corner - start).angle - angle_to_goal
                if angle_to_corner < - np.pi:  # Corner not in front of us
                    angle_to_corner += 2 * np.pi
                direction = int(angle_to_corner < 0)
                if np.abs(max_angles[direction]) <= np.abs(angle_to_corner):
                    max_angles[direction] = angle_to_corner
                    corner_points[direction] = (corner, corner_location)
        best_direction = int(max_angles[0] >= -max_angles[1])
        best_corner = corner_points[best_direction][0]
        obstacle_repulsion = np.sign(np.array(corner_points[best_direction][1]) - 0.5)
        return best_corner + Point(obstacle_repulsion) * safe_distance

    def collective_update(self):
        self.scene.move_pedestrians()
        for pedestrian in self.scene.pedestrian_list:
            if self.scene.alive_array[pedestrian.counter]:
                pedestrian.update_position()
                # assert self.scene.is_accessible(pedestrian.position)
                checkpoint_reached = pedestrian.move_to_position(Point(pedestrian.line.end), self.scene.dt)
                if checkpoint_reached:
                    done = pedestrian.is_done()
                    if done:
                        self.scene.remove_pedestrian(pedestrian)
                    else:
                        pedestrian.line = pedestrian.path.pop_next_segment()
                        pedestrian.velocity = Velocity(pedestrian.line.end - pedestrian.position.array)
                else:
                    pass


class GraphPlanner(Planner):
    def __init__(self, scene):
        self.scene = scene
        self.graph = None
        self._create_obstacle_graph(self.scene.exit_obs)
        fyi("Started preprocessing global paths")
        for pedestrian in scene.pedestrian_list:
            pedestrian.path = self.create_path(pedestrian, self.scene.exit_obs)
            pedestrian.line = pedestrian.path.pop_next_segment()
            pedestrian.velocity = Velocity(pedestrian.line.end - pedestrian.position.array)
        fyi("Finished preprocessing global paths")

    def create_path(self, pedestrian: Pedestrian, goal_obstacle) -> Path:
        ped_graph = nx.Graph(self.graph)
        ped_graph.add_node(pedestrian.position)
        self._fill_with_required_edges(pedestrian.position, ped_graph, goal_obstacle)
        try:
            path = nx.astar_path(ped_graph, pedestrian.position, goal_obstacle)
        except nx.NetworkXNoPath:
            raise RuntimeError("No path could be found from %s to exit. Check your obstacles" % pedestrian)
        path_to_exit = Path([])
        prev_point = path[0]
        if len(path) < 2:
            print(path, pedestrian)
        for point in path[1:-1]:
            line = LineSegment([prev_point, point])
            path_to_exit.append(line)
            prev_point = point
        finish_point = Planner.get_goal(prev_point, goal_obstacle)
        line_to_finish = LineSegment([prev_point, finish_point])
        # assert self.line_crosses_no_obstacles(line_to_finish)
        path_to_exit.append(line_to_finish)
        # print ("Path: %s\nPath obj %s"%(path,path_to_exit))
        return path_to_exit

    def _create_obstacle_graph(self, goal_obstacle):
        self.graph = nx.Graph()
        self.graph.add_node(goal_obstacle)
        for obstacle in self.scene.obstacle_list:
            if obstacle.in_interior and not obstacle.permeable:
                ordered_list = [corner + margin for corner, margin in zip(obstacle.corner_list, obstacle.margin_list)]
                for point in ordered_list:
                    if all(point.array < self.scene.size.array):
                        self.graph.add_node(point)
        for node in self.graph.nodes():
            if node is not goal_obstacle:
                self._fill_with_required_edges(node, self.graph, goal_obstacle)

    def _fill_with_required_edges(self, node: Point, graph, goal_obstacle):
        goal_point = Planner.get_goal(node, goal_obstacle)
        line_to_goal = LineSegment([node, goal_point])
        path_free = True
        for obstacle in self.scene.obstacle_list:
            if obstacle.in_interior and line_to_goal.crosses_obstacle(obstacle, open_sets=True):
                path_free = False
                break
        if path_free:
            graph.add_edge(u=node, v=goal_obstacle, weight=line_to_goal.length)
        for other_node in graph.nodes():
            if (other_node is not node) and (other_node is not goal_obstacle):
                path = LineSegment([node, other_node])
                path_free = True
                for obstacle in self.scene.obstacle_list:
                    if obstacle.in_interior and path.crosses_obstacle(obstacle, open_sets=True):
                        path_free = False
                        break
                if path_free:
                    graph.add_edge(u=node, v=other_node, weight=path.length)

    def draw_graph(self, graph):
        pos = {}
        for node in graph.nodes():
            position = None
            if isinstance(node, Coordinate):
                position = node.array
            elif isinstance(node, Obstacle):
                position = (node.begin + node.end) * 0.5
            else:
                raise ValueError("Unable to plot %s node type" % type(node))
            pos[node] = position
        nx.draw_networkx_nodes(graph, pos)
        nx.draw_networkx_edges(graph, pos)

        # def line_crosses_no_obstacles(self, line: LineSegment) -> bool:
        #     for obstacle in self.scene.obstacle_list:
        #         if obstacle.in_interior and line.crosses_obstacle(obstacle, open_sets=True):
        #             return False
        #     return True


if __name__ == '__main__':
    from geometry import Size
    import scene
    from planner import GraphPlanner

    scene = scene.Scene(size=Size([70, 70]), obstacle_file='demo_obstacle_list.json',
                        pedestrian_number=1)
    planner = GraphPlanner(scene)
    planner.draw_graph(planner.graph)