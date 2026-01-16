#!/usr/bin/env python3
"""
Script to download all graph images from Modal volume
"""

import subprocess
import os

# List of all task directories
tasks = [
    "20251025_041944_Put_a_pen_into_the_box_Box_100426_2025-10-25-04-18-01",
    "Drive_to_the_red_bin_and_pick_the_nearest_cube_Box_100426_2025-11-07-17-16-18",
    "Drive_to_the_red_bin_and_pick_the_nearest_cube_Box_100426_2025-11-07-17-19-44",
    "Find_screwdriver;_tighten_three_loose_screws._Box_100426_2025-11-14-16-58-12",
    "Find_screwdriver;_tighten_three_loose_screws._Box_100426_2025-11-14-17-01-19",
    "Find_screwdriver;_tighten_three_loose_screws._Box_100426_2025-11-14-17-03-05",
    "Find_screwdriver;_tighten_three_loose_screws._Box_100426_2025-11-14-17-05-49",
    "Find_screwdriver;_tighten_three_loose_screws._Box_100426_2025-11-14-17-09-21",
    "Find_screwdriver_then_tighten_three_loose_screws_Box_100426_2025-11-14-17-13-32",
    "Find_screwdriver_then_tighten_three_loose_screws_Box_100426_2025-11-14-17-15-58",
    "Find_screwdriver_then_tighten_three_loose_screws_Box_100426_2025-11-14-17-17-57",
    "Find_screwdriver_then_tighten_three_loose_screws_Box_100426_2025-11-14-17-21-07",
    "Find_screwdriver_then_tighten_three_loose_screws_Box_100426_2025-11-14-17-24-41",
    "Find_screwdriver_then_tighten_three_loose_screws_Box_100426_2025-11-14-17-27-32",
    "Leave_the_room_through_the_closed_door_Box_100426_2025-10-31-14-41-01",
    "Open_box_lid_then_place_cube_inside_then_close_box_Box_100426_2025-11-21-16-47-40",
    "Open_box_lid_then_place_cube_inside_then_close_box_Box_100426_2025-11-21-16-56-43",
    "Open_box_lid_then_place_cube_inside_then_close_box_Box_100426_2025-11-21-16-58-25",
    "Open_box_lid_then_place_cube_inside_then_close_box_Box_100426_2025-11-21-17-02-19",
    "Open_box_lid_then_place_cube_inside_then_close_box_Box_100426_2025-11-21-17-08-26",
    "Pick_up_the_blue_cube._Box_100426_2025-11-14-06-02-21",
    "Pick_up_the_blue_cube._Box_100426_2025-11-14-06-11-45",
    "Pick_up_the_blue_cube._Box_100426_2025-11-14-06-17-59",
    "Pick_up_the_cup,_pour_liquid,_and_set_it_down_Box_100426_2025-11-21-17-26-51",
    "Place_the_cube_on_the_blue_platform_Box_100426_2025-11-07-17-25-31",
    "Place_the_cube_on_the_blue_platform_Box_100426_2025-11-07-17-28-39",
    "Place_the_cube_on_the_blue_platform_Box_100426_2025-11-07-17-31-26",
    "Put_a_pen_into_the_box_Box_100426_2025-10-25-04-37-36",
    "Put_a_pen_into_the_box_Box_100426_2025-10-25-16-53-44",
    "Put_a_pen_into_the_box_Box_100426_2025-10-25-16-56-50",
    "Put_a_pen_into_the_box_Box_100426_2025-10-25-16-58-19",
    "Put_a_pen_into_the_box_Box_100426_2025-10-25-17-42-44",
    "Put_a_pen_into_the_box_Box_100426_2025-10-25-18-12-21",
    "Put_a_pen_into_the_box_Box_100426_2025-10-25-18-15-10",
    "Put_a_pen_into_the_box_Box_100426_2025-10-25-18-17-44",
    "Put_a_pen_into_the_box_Box_100426_2025-10-25-23-54-27",
    "Put_a_pen_into_the_box_Box_100426_2025-10-25-23-55-24",
    "Put_a_pen_into_the_box_Box_100426_2025-10-26-00-06-06",
    "Put_a_pen_into_the_box_Box_100426_2025-10-26-00-13-55",
    "Put_a_pen_into_the_box_Box_100426_2025-10-26-00-15-36",
    "Put_a_pen_into_the_box_Box_100426_2025-10-26-02-10-04",
    "Stack_two_green_blocks_on_the_yellow_pallet_Box_100426_2025-11-07-17-46-17",
    "Stack_two_green_blocks_on_the_yellow_pallet_Box_100426_2025-11-07-17-51-13",
    "Turn_on_the_coffee_machine_Box_100426_2025-10-31-14-18-31",
    "Turn_on_the_coffee_machine_Box_100426_2025-10-31-14-21-47",
    "Turn_on_the_coffee_machine_Box_100426_2025-10-31-14-23-47",
    "Turn_on_the_coffee_machine_Box_100426_2025-10-31-14-25-49",
    "Turn_on_the_coffee_machine_Box_100426_2025-10-31-14-28-04",
    "Turn_on_the_lamp_Box_100426_2025-10-31-14-42-53",
    "Turn_on_the_lamp_Box_100426_2025-10-31-14-45-12",
    "Turn_on_the_lamp_Box_100426_2025-10-31-14-46-51",
    "Turn_on_the_lamp_Box_100426_2025-10-31-14-49-41",
    "pick_up_the_cup_then_pour_the_liquid_then_set_it_down_Box_100426_2025-11-21-17-29-16",
    "pick_up_the_cup_then_pour_the_liquid_then_set_it_down_Box_100426_2025-11-21-17-32-56",
    "pour_liquid_task_Box_100426_2025-11-21-17-34-56",
    "pour_liquid_task_Box_100426_2025-11-21-17-38-02",
    "put_the_box_in_the_middle_of_the_table_Box_100426_2025-10-25-17-03-56",
]


def main():
    # Set up environment
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    # Create output directory
    os.makedirs("task_graphs", exist_ok=True)

    print("Downloading graphs from Modal volume...")
    print(f"Total tasks: {len(tasks)}")
    print()

    success = 0
    failed = 0

    for idx, task in enumerate(tasks, 1):
        graph_file = f"{task}_graph.png"
        remote_path = f"{task}/{graph_file}"
        local_path = f"task_graphs/{graph_file}"

        print(f"[{idx}/{len(tasks)}] Downloading: {task}")

        try:
            # Run modal volume get command
            result = subprocess.run(
                [
                    "modal",
                    "volume",
                    "get",
                    "robogen-generated_task_outputs",
                    remote_path,
                    local_path,
                ],
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )

            if result.returncode == 0:
                print(f"  [OK] Success")
                success += 1
            else:
                print(f"  [FAIL] Failed (graph may not exist)")
                failed += 1
        except Exception as e:
            print(f"  [ERROR] Error: {e}")
            failed += 1

    print()
    print("=" * 50)
    print("Download Summary")
    print("=" * 50)
    print(f"Total: {len(tasks)}")
    print(f"Success: {success}")
    print(f"Failed: {failed}")
    print(f"\nGraphs saved to: task_graphs/")


if __name__ == "__main__":
    main()
