"""Tiny CLI: atlasbridge chat "Sannu"  |  atlasbridge translate --to yo "Good morning"."""

import argparse
import sys

from .client import AtlasBridge, AtlasBridgeError


def main() -> None:
    p = argparse.ArgumentParser(prog="atlasbridge", description="Talk to N-ATLaS from your terminal.")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("chat", help="Ask N-ATLaS something (streams the reply)")
    c.add_argument("prompt")
    t = sub.add_parser("translate", help="Translate between en/ha/ig/yo")
    t.add_argument("--to", required=True)
    t.add_argument("--from", dest="source", default="auto")
    t.add_argument("text")
    d = sub.add_parser("detect", help="Detect the language of some text")
    d.add_argument("text")
    args = p.parse_args()

    try:
        with AtlasBridge() as ab:
            if args.cmd == "chat":
                for piece in ab.stream(args.prompt):
                    print(piece, end="", flush=True)
                print()
            elif args.cmd == "translate":
                print(ab.translate(args.text, to=args.to, source=args.source))
            else:
                r = ab.detect_language(args.text)
                print(f"{r['name']} ({r['language']})")
    except (AtlasBridgeError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
