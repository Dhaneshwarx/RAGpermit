"""Run every offline suite, plus local model checks with --live."""
import argparse
import subprocess
import sys
from pathlib import Path

OFFLINE = ('test_loader_refusals', 'test_access_matrix', 'test_auth',
           'test_auth_breaks', 'test_signin', 'test_mcp', 'test_mcp_breaks')
LIVE = ('test_retrieval', 'test_answers', 'test_audit')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Also test Ollama and the ingested store')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    commands = [[sys.executable, '-m', 'unittest', 'tests.test_passwords',
                 'tests.test_setup_password', 'tests.test_password_login', 'tests.test_cli_errors', 'tests.test_web']]
    commands += [[sys.executable, '-m', 'tests.' + name]
                 for name in OFFLINE + (LIVE if args.live else ())]
    failed = []
    for command in commands:
        print('\nRunning ' + ' '.join(command[2:]), flush=True)
        if subprocess.run(command, cwd=root).returncode:
            failed.append(command[-1])
    print('\n' + ('FAILED: ' + ', '.join(failed) if failed else 'All requested suites passed.'))
    return bool(failed)


if __name__ == '__main__':
    sys.exit(main())
