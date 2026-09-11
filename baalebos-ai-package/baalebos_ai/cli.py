import sys
import argparse

from .client import BaalebosAI
from .auth import AuthError


def main():
    parser = argparse.ArgumentParser(description="Baalebos AI Gateway Terminal CLI")
    parser.add_argument("prompt", nargs="*", help="The prompt to send to the AI gateway")
    parser.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "manual", "fanout", "fallback"],
        help="Execution mode (default: auto)",
    )
    args = parser.parse_args()

    if not args.prompt:
        print('Usage: ai "Your prompt here"')
        sys.exit(1)

    full_prompt = " ".join(args.prompt)
    try:
        client = BaalebosAI()
        response = client.chat(prompt=full_prompt, mode=args.mode)
        print("\n" + response + "\n")
    except AuthError as e:
        print(f"Could not set up your API key automatically: {e}", file=sys.stderr)
        print(
            "You can also set one manually: export BAALEBOS_API_KEY=your_key",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
