"""打包明确列举的 CLI 和网站集成源码，永不包含本地配置或凭据。"""

import hashlib
import json
import zipfile

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLUGIN = ROOT / 'backend/plugin/openauth'
SKILL_FILES = (
    'SKILL.md',
    'runtime.json',
    'references/auth.md',
    'references/calculation.md',
    'references/qbank.md',
    'lib/openauth.cjs',
    'lib/messages.cjs',
    'lib/package.cjs',
    'lib/commands/calculation.cjs',
    'lib/commands/qbank.cjs',
    'scripts/youanshang.cjs',
    'scripts/install.cjs',
    'scripts/install.sh',
    'scripts/uninstall.cjs',
    'scripts/uninstall.sh',
)
WEB_FILES = (
    'app/pages/openauth/authorize.vue',
    'app/pages/openauth/authorizations.vue',
    'app/pages/openauth/revoke.vue',
    'app/utils/openauth.ts',
    'app/middleware/openauth.global.ts',
    'app/plugins/analytics.client.ts',
    'server/middleware/openauth-security.ts',
    'tests/openauth.test.ts',
    'tsconfig.openauth.json',
)


def package_sources() -> dict:
    output = PLUGIN / 'artifacts'
    output.mkdir(exist_ok=True)
    archives = {
        'youanshang-skill.zip': [(ROOT / 'skills/youanshang' / name, f'youanshang/{name}') for name in SKILL_FILES],
        'openauth-web-integration.zip': [(ROOT / 'web' / name, f'web/{name}') for name in WEB_FILES]
        + [(PLUGIN / 'docs/local-quickstart.md', 'LOCAL-QUICKSTART.md')],
    }
    manifest = {}
    for name, files in archives.items():
        target = output / name
        with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for source, archive_name in files:
                if not source.is_file() or source.is_symlink():
                    raise ValueError(f'必须使用普通源码文件: {source}')
                archive.write(source, arcname=archive_name)
        with zipfile.ZipFile(target) as archive:
            if archive.testzip() is not None:
                raise ValueError(f'归档验证失败: {name}')
            manifest[name] = {'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'files': archive.namelist()}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    source = ROOT / 'skills/youanshang'
    release = {
        'version': json.loads((source / 'runtime.json').read_text(encoding='utf-8'))['version'],
        'package_path': 'skill-package',
        'sha256': manifest['youanshang-skill.zip']['sha256'],
        'files': {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in SKILL_FILES},
    }
    (output / 'skill-release.json').write_text(json.dumps(release, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    print(json.dumps(package_sources(), indent=2, ensure_ascii=False))
