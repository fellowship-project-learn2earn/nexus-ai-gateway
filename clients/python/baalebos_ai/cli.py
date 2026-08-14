import sys
import argparse
from baalebos_ai.client import BaalebosAI


def main():
    parser = argparse.ArgumentParser(description='Baalebos AI Gateway Terminal CLI')
    parser.add_argument('prompt', nargs='*', help='The prompt to send to the AI gateway')
    parser.add_argument('--mode', default='auto', help='Execution mode (auto, fast, smart)')
    args = parser.parse_args()

    if not args.prompt:
        print('Usage: ai "Your prompt here"')
        sys.exit(1)

    full_prompt = ' '.join(args.prompt)
    try:
        client = BaalebosAI()
        response = client.chat(prompt=full_prompt, mode=args.mode)
        print('\n' + response + '\n')
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
