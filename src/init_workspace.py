"""Initialize an empty private workspace, without demo accounts or documents."""
import argparse
import json
from pathlib import Path


def initialize(root):
    root = Path(root).expanduser()
    if not root.is_absolute():
        raise ValueError('Use an absolute workspace path.')
    # Never overwrite or merge with an existing workspace.
    root.mkdir(parents=True, exist_ok=False)
    (root / 'data' / 'docs').mkdir(parents=True)
    (root / 'data' / 'users.json').write_text(json.dumps([]) + '\n', encoding='utf-8')
    (root / '.gitignore').write_text('*\n', encoding='utf-8')
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', help='New absolute folder path, outside the project repository')
    args = parser.parse_args()
    try:
        root = initialize(args.folder)
    except (OSError, ValueError) as error:
        parser.exit(1, 'Workspace not created: ' + str(error) + '\n')
    print('Empty workspace created at ' + str(root))
    print('Set PERMITRAG_WORKSPACE to this path before all PermitRAG commands.')
    print('Next: configure real user records and document permissions before ingestion.')


if __name__ == '__main__':
    main()
