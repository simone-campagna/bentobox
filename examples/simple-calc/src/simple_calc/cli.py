import argparse
import operator

from . import calc

def main_add():
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=int)
    parser.add_argument("right", type=int)
    ns = parser.parse_args()
    print("SIMPLE-ADD> {} + {} = {}".format(ns.left, ns.right, ns.left + ns.right))
    return 0


def main_sub():
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=int)
    parser.add_argument("right", type=int)
    ns = parser.parse_args()
    print("SIMPLE-SUB> {} - {} = {}".format(ns.left, ns.right, ns.left - ns.right))
    return 0


def main_mul():
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=int)
    parser.add_argument("right", type=int)
    ns = parser.parse_args()
    print("SIMPLE-MUL> {} x {} = {}".format(ns.left, ns.right, ns.left * ns.right))
    return 0


def main_div():
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=int)
    parser.add_argument("right", type=int)
    ns = parser.parse_args()
    print("SIMPLE-DIV> {} / {} = {}".format(ns.left, ns.right, ns.left / ns.right))
    return 0


def main_pow():
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=int)
    parser.add_argument("right", type=int)
    ns = parser.parse_args()
    print("SIMPLE-POW> {} ^ {} = {}".format(ns.left, ns.right, ns.left ** ns.right))
    return 0


def main_calc():
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=int)
    parser.add_argument(
        "operator",
        choices=list(calc.OPS),
    )
    parser.add_argument("right", type=int)
    ns = parser.parse_args()
    print("SIMPLE-CALC> {} {} {} = {}".format(ns.left, ns.operator, ns.right, calc.calc(ns.left, ns.operator, ns.right)))
    return 0


if __name__ == "__main__":
    main()
