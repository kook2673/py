import os
from convert_encoding_to_utf8 import convert_file, should_process


def run(add_bom: bool = True) -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    # Target: 유튜브/Quick Share/[무협,판타지]
    src_root = os.path.join(repo_root, '유튜브', 'Quick Share', '[무협,판타지]')
    dst_root = os.path.join(repo_root, '유튜브', 'Quick Share', '[무협,판타지]_UTF8')

    print(f'SOURCE: {src_root}')
    print(f'DEST  : {dst_root}')

    if not os.path.exists(src_root):
        print('ERROR: Source folder not found')
        return

    processed = 0
    failures = 0

    for dirpath, _, filenames in os.walk(src_root):
        for name in filenames:
            if not should_process(name):
                continue
            src_path = os.path.join(dirpath, name)
            rel = os.path.relpath(src_path, src_root)
            dst_path = os.path.join(dst_root, rel)
            result = convert_file(src_path, dst_path, add_bom)
            processed += 1
            if result is None or not result.startswith('OK:'):
                failures += 1
                print(f"FAIL\t{rel}\t{result}")
            else:
                print(f"OK\t{rel}\t{result}")

    print(f"SUMMARY\tprocessed={processed}\tfailures={failures}\tdst={dst_root}")


if __name__ == '__main__':
    run(add_bom=True)


