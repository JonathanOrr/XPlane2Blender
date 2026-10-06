import argparse
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import time

REPO_DIR = os.path.dirname(os.path.realpath(__file__))
TESTS_DIR = os.path.join(REPO_DIR, "tests")
TMP_DIR = os.path.join(TESTS_DIR, "tmp")


def clean_tmp_folder():
    # create temp dir if not exists
    os.makedirs(TMP_DIR, exist_ok=True)

    # Thanks jgoeders for something short,
    # https://stackoverflow.com/a/6615332
    for file_object in os.listdir(TMP_DIR):
        file_object_path = os.path.join(TMP_DIR, file_object)
        if os.path.isfile(file_object_path) or os.path.islink(file_object_path):
            os.unlink(file_object_path)
        else:
            shutil.rmtree(file_object_path)


def _make_argparse():
    parser = argparse.ArgumentParser(description="Runs the XPlane2Blender test suite")
    test_selection = parser.add_argument_group("Test Selection And Control")
    test_selection.add_argument(
        "-f", "--filter", help="Filter test files with a regular expression", type=str
    )  # [regex]
    test_selection.add_argument(
        "-s",
        "--start-at",
        help="Start in list of files to test at first matching a regular expression",
        type=str,
    )  # [regex]
    test_selection.add_argument(
        "--exclude", help="Exclude test files with a regular expression", type=str
    )  # [regex]
    test_selection.add_argument(
        "-c",
        "--continue",
        help="Keep running after a test failure",
        default=False,
        action="store_true",
        dest="keep_going",
    )
    test_selection.add_argument(
        "-j",
        "--jobs",
        help="Number of test files to run at once (default: number of CPUs)",
        type=int,
        default=os.cpu_count() or 1,
    )

    output_control = parser.add_argument_group("Output Control")
    output_control.add_argument(
        "-q",
        "--quiet",
        default=False,
        help="Only output if tests pass or fail",
        action="store_true",
    )
    output_control.add_argument(
        "-p",
        "--print-fails",
        default=False,
        help="Like --quiet, but also prints the output of failed tests",
        action="store_true",
    )
    # Hopefully it could one day also enable pydev, and we can move this to a --verbose argument
    output_control.add_argument(
        "--force-xplane-debug",
        default=False,
        help="Shows verbose(!) debug info and turns on Scene's Debug if not set in Blend file",
        action="store_true",
    )

    blender_options = parser.add_argument_group("Blender Options")

    blender_options.add_argument(
        "--blender",
        default="blender",  # Use the blender in the system path
        type=str,
        help="Provide alternative path to Blender executable",
    )
    blender_options.add_argument(
        "--force-blender-debug",
        help="Turn on Blender's --debug flag",
        action="store_true",
    )
    blender_options.add_argument(
        "-n",
        "--no-factory-startup",
        help="Run Blender with current prefs rather than factory prefs",
        action="store_true",
    )
    return parser


def main(argv=None) -> int:
    """
    Return is exit code, 0 for good, anything else is an error
    """
    exit_code = 0

    """
    Rather than mess with fancy ways to pass back test results
    we have a stupid simple solution: Print a special string
    at the end and parse it here.

    Unfortunately, the REGEX must be duplicated across both files
    due to some problems with importing it from the test module
    """
    TEST_RESULTS_REGEX = re.compile(
        r"RESULT: After (?P<testsRun>\d+) tests got (?P<errors>\d+) errors, (?P<failures>\d+) failures, and (?P<skipped>\d+) skipped"
    )

    # Accumulated TestResult stats, reported at the end of everything
    total_testsCompleted, total_errors, total_failures, total_skipped = (0,) * 4
    timer_start = time.perf_counter()

    clean_tmp_folder()
    if argv is None:
        argv = _make_argparse().parse_args(sys.argv[1:])
        if argv.filter:
            argv.filter = re.escape(argv.filter)
        if argv.start_at:
            argv.start_at = re.escape(argv.start_at)
        if argv.exclude:
            argv.exclude = re.escape(argv.exclude)

    if shutil.which(argv.blender) is None:
        print(
            f"Blender executable '{argv.blender}' not found, use --blender /path/to/blender"
        )
        return 1

    def printTestBeginning(text):
        """
        Print the C-Style and Vim comment block start tokens
        so that text editors can recognize places to automatically fold up the tests
        """

        # Why the hex escapes? So we don't fold our own code!
        print(("\x2F*=== " + text + " ").ljust(75, "=") + "\x7B\x7B\x7B")

    def printTestEnd():
        """
        Print the C-Style and Vim comment block end tokens
        so that text editors can recognize places to automatically fold up the tests
        """
        print(("=" * 75) + "}}}*/")

    def inFilter(filepath: str) -> bool:
        """
        Tests if filepath matches --filter and/or --exclude,
        always returns False if --start-at hasn't been satisfied yet
        """
        if argv.start_at is None:
            inFilter.should_start_taking = True  # type: bool
        elif getattr(inFilter, "should_start_taking", None) is None:
            inFilter.should_start_taking = False

        if inFilter.should_start_taking is False:
            inFilter.should_start_taking = bool(
                argv.start_at and re.search(argv.start_at, filepath)
            )
            if inFilter.should_start_taking is False:
                # We still haven't found it!
                return False

        passes = True

        if argv.filter is not None:
            passes &= bool(re.search(argv.filter, filepath))

        if argv.exclude is not None:
            passes &= not re.search(argv.exclude, filepath)

        return passes

    test_files = []
    for root, dirs, files in os.walk(TESTS_DIR):
        dirs.sort()
        for file in sorted(files):
            pyFile = os.path.join(root, file)
            if file.endswith(".test.py") and inFilter(
                os.path.relpath(pyFile, REPO_DIR).replace(os.sep, "/")
            ):
                test_files.append(pyFile)

    # Environment variables - in order for --addons to work, we need to have OUR folder
    # exist, and we need to have "addons/modules" simlink BACK to us to create the illusion
    # of the directory structure Blender expects. Config goes to a scratch folder so
    # tests never read or write the user's real Blender preferences.
    enviro = {
        **os.environ,
        "BLENDER_USER_SCRIPTS": REPO_DIR,
        "BLENDER_USER_CONFIG": os.path.join(TMP_DIR, "blender_config"),
    }

    def run_test_file(pyFile: str) -> str:
        blendFile = pyFile.replace(".py", ".blend")
        blender_args = [
            argv.blender,
            "--addons",
            "io_xplane2blender",
            "--factory-startup",
            "-noaudio",
            "-b",
        ]

        if argv.no_factory_startup:
            blender_args.remove("--factory-startup")

        out = ""
        if os.path.exists(blendFile):
            blender_args.append(blendFile)
        elif not (argv.quiet or argv.print_fails):
            out += "WARNING: Blender file " + blendFile + " does not exist\n"

        blender_args.extend(["--python", pyFile])

        if argv.force_blender_debug:
            blender_args.append("--debug")

        # Small Hack!
        # Blender stops parsing after '--', so we can append the test runner
        # args and bridge the gap without anything fancy!
        blender_args.extend(["--"] + sys.argv[1:])

        if not argv.quiet and (argv.force_blender_debug or argv.force_xplane_debug):
            # print the command used to execute the script
            # to be able to easily re-run it manually to get better error output
            out += " ".join(blender_args) + "\n"

        # Run Blender, normalize output line endings because Windows is dumb.
        # A crash or non-zero exit is reported below as a missing results line.
        proc = subprocess.run(
            blender_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            errors="replace",
            env=enviro,
            cwd=REPO_DIR,
        )
        blender_out = proc.stdout
        if proc.returncode != 0:
            blender_out += f"\nBlender exited with code {proc.returncode}"
        return out + blender_out

    exit_code = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, argv.jobs)) as pool:
        # Results are reported in file order, whatever order they finish in
        futures = [(pyFile, pool.submit(run_test_file, pyFile)) for pyFile in test_files]
        for pyFile, future in futures:
            if exit_code != 0:
                future.cancel()
                continue

            pyFile = os.path.relpath(pyFile, REPO_DIR)
            out = future.result()

            if not (argv.quiet or argv.print_fails):
                printTestBeginning("Running file " + pyFile)

            if not argv.force_blender_debug:
                # Ignore the junk!
                pattern = "^(%s)" % "|".join(
                    (
                        "DAG zero",
                        "found bundled python",
                        "Read new prefs",
                        "ID user decrement error",
                        "Smart Projection time",
                        "WARNING.*has no UV-Map.",
                        "ERROR.*wrong user count in old ID",
                    )
                )

                out = "\n".join(
                    filter(lambda line: not re.match(pattern, line), out.splitlines())
                )
            if not (argv.quiet or argv.print_fails):
                print(out)

            # TestResults from the current test
            testsRun, errors, failures, skipped = (0,) * 4
            results = re.search(TEST_RESULTS_REGEX, out)
            if not results:
                # The test file never got to print its results:
                # Blender crashed, or the test script raised before finishing
                print(
                    "Test runner must print correct results string at end or have suffered an unrecoverable error"
                )
                total_errors += 1
                errors = 1
            else:
                testsRun, errors, failures, skipped = (
                    int(results.group("testsRun")),
                    int(results.group("errors")),
                    int(results.group("failures")),
                    int(results.group("skipped")),
                )

                total_testsCompleted += testsRun
                total_errors += errors
                total_failures += failures
                total_skipped += skipped

            if errors or failures:
                if argv.print_fails:
                    printTestBeginning("Running file %s - FAILED" % (pyFile))
                    print(out)
                    printTestEnd()
                else:
                    print("%s FAILED" % pyFile)

                if not argv.keep_going:
                    exit_code = 1
            elif argv.quiet or argv.print_fails:
                print("%s passed" % pyFile)

            # THIS IS THE LAST THING TO PRINT BEFORE A TEST ENDS
            # Its a little easier to see the boundaries between test suites,
            # given that there is a mess of print statements from Python, unittest, the XPlane2Blender logger,
            # Blender, and more in there sometimes
            if not (argv.quiet or argv.print_fails):
                printTestEnd()

    # Final Result String Benifits
    # - --continue concisely tells how many tests failed
    # - Just enough more info for --quiet
    # - No matter what uselles noise Blender and unittset spit out the
    # end of the log has the final answer
    print(
        (
            "FINAL RESULTS: {total_testsCompleted} {test_str} completed,"
            " {total_errors} errors,"
            " {total_failures} failures,"
            " {total_skipped} skipped. Finished in {total_seconds:.4f} seconds"
        ).format(
            total_testsCompleted=total_testsCompleted,
            test_str="test case" if total_testsCompleted == 1 else "tests cases",
            total_errors=total_errors,
            total_failures=total_failures,
            total_skipped=total_skipped,
            total_seconds=time.perf_counter() - timer_start,
        )
    )
    # --continue only decides whether to keep going; any failure still fails the run
    return 1 if exit_code or total_errors or total_failures else 0


if __name__ == "__main__":
    sys.exit(main())
