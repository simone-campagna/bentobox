import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    ns = parser.parse_args()
    print("Hello, {}!".format(ns.name))
    return 0


if __name__ == "__main__":
    main()
