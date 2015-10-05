__author__ = 'omar'

import argparse
import sys

sys.path.insert(1, 'src')
from geometry import Size, Point
import scene as scene_module
import functions
from results import Result
from visualization import VisualScene
from dynamic_planner import DynamicPlanner
from grid_computer import GridComputer
from static_planner import GraphPlanner
from scene_cases import LoopScene, TwoImpulseScene

# Default parameters
number_of_pedestrians = 100
domain_width = 70
domain_height = 70
obstacle_file = 'scenes/demo_obstacle_list.json'
# Command line parameters
parser = argparse.ArgumentParser(description="Prototype Crowd Dynamics Simulation")
parser.add_argument('-n', '--number', type=int, help='Number of pedestrians in simulation',
                    default=number_of_pedestrians)
parser.add_argument('-s', '--step', action='store_true', help='Let simulation progress on mouse click only')
parser.add_argument('-p', '--plot', action='store_true', help='Let simulation plot global values on each time step')
parser.add_argument('-c', '--apply-interpolation', action='store_true',
                    help='Let simulation impose swarm behaviour to the pedestrians')
parser.add_argument('-u', '--apply-pressure', action='store_true',
                    help='Let simulation impose UIC (pressure term) to the pedestrians (-c implied)')
parser.add_argument('-x', '--width', type=int, help='Width of the simulation domain', default=domain_width)
parser.add_argument('-y', '--height', type=int, help='Height of the simulation domain', default=domain_height)
parser.add_argument('-d', '--delay', type=int, help='Delay between time steps (in milliseconds)', default=1)
parser.add_argument('-o', '--obstacle-file', type=str, help='JSON file containing obstacle descriptions',
                    default=obstacle_file)
parser.add_argument('-i', '--impulse', action='store_true', help='Order pedestrians in an impulse')
parser.add_argument('-l', '--loop', action='store_true', help='Pedestrians reappear on the other side (experimental)')
parser.add_argument('-r', '--results', action='store_true', help='Log results of simulation to disk')
parser.add_argument('-v', '--verbose', action='store_true', help='Print debugging information to console')
parser.add_argument('-a', '--dynamic', action='store_true', help='Apply the dynamic planner to pedestrians')

args = parser.parse_args()

# Initialization
functions.VERBOSE = args.verbose
if args.impulse:
    # scene = ImpulseScene(size=Size([args.width, args.height]), obstacle_file=args.obstacle_file,
    #                    pedestrian_number=args.number, impulse_location=Point([35, 50]), impulse_size=45)

    scene = TwoImpulseScene(size=Size([args.width, args.height]), obstacle_file=args.obstacle_file,
                            pedestrian_number=args.number, impulse_locations=[Point([40, 20]), Point([30, 20])],
                            impulse_size=45)
elif args.loop:
    scene = LoopScene(size=Size([args.width, args.height]), obstacle_file='hall.json', pedestrian_number=args.number)
    # Integrate in scene
else:
    scene = scene_module.Scene(size=Size([args.width, args.height]), obstacle_file=args.obstacle_file,
                            pedestrian_number=args.number)

if args.dynamic:
    dynamic_planner = DynamicPlanner(scene, args.plot)
    step_functions = [dynamic_planner.step]
else:
    planner = GraphPlanner(scene)
    grid = GridComputer(scene, show_plot=args.plot, apply_interpolation=args.apply_interpolation,
                        apply_pressure=args.apply_pressure)
    step_functions = [planner.collective_update, grid.step]
if args.results:
    result = Result(scene)

vis = VisualScene(scene, 1500, 1000, step_functions=step_functions, loop=not args.step, delay=args.delay)

# Running
vis.loop()
vis.window.mainloop()
scene.finish()
