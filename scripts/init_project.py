"""生成 Seek 私有部署配置，保留已有值并验证真实安全输入。"""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from seek.shared.web_providers import SEARCH_PROVIDER_IDS

SECURITY_KEYS = ('JWT_SECRET_KEY', 'API_KEY_DERIVATION_SECRET')


def _decode(value: str, key: str) -> str:
    """解析单行 dotenv 的字面值，不执行 shell 或环境变量展开。"""
    value = value.strip()
    if not value or value.startswith('#'):
        return ''
    if value.startswith('"'):
        try:
            result, end = json.JSONDecoder().raw_decode(value)
        except ValueError as exc:
            raise ValueError(f'{key}: unterminated quote or invalid escape') from exc
        rest = value[end:].strip()
        if rest and not rest.startswith('#'):
            raise ValueError(f'{key}: unexpected text after quote')
        return result
    if value.startswith("'"):
        result = []
        index = 1
        while index < len(value):
            if value[index:index+2] == "\\'":
                result.append("'");index += 2
            elif value[index] == "'":
                rest = value[index+1:].strip()
                if rest and not rest.startswith('#'):
                    raise ValueError(f'{key}: unexpected text after quote')
                return ''.join(result)
            else:
                result.append(value[index]);index += 1
        raise ValueError(f'{key}: unterminated quote')
    return re.sub(r'\s+#.*$', '', value).strip()


def _values(lines: list[str]) -> dict[str, str]:
    """读取最终赋值，错误只报告字段名。"""
    result = {}
    for line in lines:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.fullmatch(r'\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*=(.*)', line)
        if not match:
            raise ValueError('配置行格式无效')
        raw = match[2]
        if match[1] in SECURITY_KEYS and raw and not raw.lstrip().startswith(('"', "'", '#')):
            value = re.sub(r'\s+#.*$', '', raw)
            if value.strip() and value != value.strip():
                raise ValueError(f'{match[1]} 不能包含边缘空白')
        result[match[1]] = _decode(raw, match[1])
    return result


def validate_security(values: dict[str, str]) -> None:
    """拒绝短值、边缘空白、多行和复用签名密钥，不输出秘密。"""
    for key in SECURITY_KEYS:
        value = values.get(key, '')
        if len(value) < 32 or value != value.strip() or any(char in value for char in '\r\n\x00'):
            raise ValueError(f'{key} 必须是至少 32 字符、无边缘空白的单行密钥')
    if values[SECURITY_KEYS[0]] == values[SECURITY_KEYS[1]]:
        raise ValueError('API_KEY_DERIVATION_SECRET 不能复用 JWT_SECRET_KEY')


def _line(key: str, value: str) -> str:
    """复杂值按真实 Compose dotenv roundtrip 已验证的格式编码。"""
    if any(char in value for char in '\r\n\x00'):
        raise ValueError(f'{key} 必须是 single-line 配置')
    encoded = value if re.fullmatch(r'[A-Za-z0-9._:/,@+=-]*', value) else json.dumps(value.replace('$', '$$'), ensure_ascii=False)
    return f'{key}={encoded}'


def initialize(root: Path) -> bool:
    """原子补齐空项；已有非空值不旋转，链接和非法输入显式拒绝。"""
    target = root / os.getenv('SEEK_ENV_FILE', '.env')
    if target.is_symlink():
        raise ValueError('拒绝符号链接配置')
    existed = target.exists()
    template = root/'.env.template'
    if not template.exists():
        template = Path(__file__).resolve().parents[1]/'.env.template'
    original = target.read_text().splitlines() if existed else template.read_text().splitlines()
    saved = _values(original)
    fields = _values(template.read_text().splitlines())
    values = dict(saved)
    if not existed:
        values.update({key:os.environ[key] for key in fields if key in os.environ})
    # 显式非空安全输入先验证，不能让生成器掩盖错误。
    for key in SECURITY_KEYS:
        if values.get(key):
            validate_security({**{name:'temporary-validation-placeholder-' + name for name in SECURITY_KEYS},key:values[key]})
    if all(values.get(key) for key in SECURITY_KEYS):
        validate_security(values)
    generated = {
        'COMPOSE_PROJECT_NAME':'seek','SEEK_INSTANCE_ID':'seek-'+secrets.token_hex(12),
        'JWT_SECRET_KEY':secrets.token_hex(32),'API_KEY_DERIVATION_SECRET':secrets.token_hex(32),
        'SEEK_ENCRYPTION_KEY':base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'POSTGRES_PASSWORD':secrets.token_hex(32),'MINIO_ACCESS_KEY':'seek'+secrets.token_hex(16),
        'MINIO_SECRET_KEY':secrets.token_hex(32),'SANDBOX_RUNNER_TOKEN':secrets.token_hex(32),
    }
    for key,default in fields.items():
        if not values.get(key):
            values[key] = generated.get(key,default)
    validate_security(values)
    if values.get('WEB_SEARCH_PROVIDER') not in SEARCH_PROVIDER_IDS:
        raise ValueError('WEB_SEARCH_PROVIDER 无效')
    output = list(original)
    assigned = {line.split('=',1)[0].strip():index for index,line in enumerate(original) if '=' in line and not line.lstrip().startswith('#')}
    for key,value in values.items():
        if existed and saved.get(key):
            continue
        encoded = _line(key,value)
        if key in assigned:
            output[assigned[key]] = encoded
        else:
            output.append(encoded)
    content = '\n'.join(output)+'\n'
    if existed and content == target.read_text():
        return False
    descriptor,temporary = tempfile.mkstemp(prefix='.seek-env-',dir=target.parent)
    try:
        with os.fdopen(descriptor,'w') as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno())
        if existed:
            os.replace(temporary,target)
        else:
            os.link(temporary,target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


def main() -> None:
    """只报告结果与字段错误，不输出凭据。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--validate-security-env',action='store_true')
    args=parser.parse_args()
    try:
        if args.validate_security_env:
            validate_security(_values((args.root/os.getenv('SEEK_ENV_FILE','.env')).read_text().splitlines()))
            print('Seek 安全配置有效。')
        else:
            print('Seek 私有配置已准备。' if initialize(args.root) else '已有私有配置，保持原样。')
    except (ValueError,OSError) as exc:
        parser.exit(1,str(exc)+'\n')


if __name__ == '__main__':
    main()
