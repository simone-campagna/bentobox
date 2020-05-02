import argparse
import operator

from calclib import compute


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=int)
    parser.add_argument(
        "operator",
        choices=list(compute.OPS),
    )
    parser.add_argument("right", type=int)
    ns = parser.parse_args()
    print("CALC> {} {} {} = {}".format(ns.left, ns.operator, ns.right, compute.compute(ns.left, ns.operator, ns.right)))
    return 0


if __name__ == "__main__":
    main()
