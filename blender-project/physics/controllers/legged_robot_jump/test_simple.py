"""Simple test controller to verify basic Webots setup."""

import sys

try:
    with open("/tmp/test_controller_output.txt", "w") as f:
        f.write("Starting test controller\n")
        f.flush()

        from controller import Robot
        f.write("Successfully imported Robot\n")
        f.flush()

        robot = Robot()
        f.write("Successfully created Robot object\n")
        f.flush()

        timestep = int(robot.getBasicTimeStep())
        f.write(f"Timestep: {timestep}\n")
        f.flush()

        for i in range(5):
            result = robot.step(timestep)
            f.write(f"Step {i}: result = {result}\n")
            f.flush()

        f.write("Test controller completed successfully\n")
        f.flush()

except Exception as e:
    with open("/tmp/test_controller_output.txt", "a") as f:
        f.write(f"Error: {e}\n")
        import traceback
        f.write(traceback.format_exc())
        f.flush()
