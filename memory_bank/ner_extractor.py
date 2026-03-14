"""
实体识别模块 (NER)

使用 jieba 分词 + 词性标注 + 自定义规则提取实体。
支持中英文混合文本。

依赖: pip install jieba
"""

import re
import jieba
import jieba.posseg as pseg
import logging
from typing import List, Set, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# 使用共享的 jieba 词典管理器
from .jieba_dict import init_jieba, add_word, tokenize


# ==================== 配置 ====================

# 停用词表（常见无意义词）
STOP_WORDS = {
    # 中文停用词
    '的是', '是在', '这个', '那个', '一个', '什么', '怎么', '如何',
    '因为', '所以', '但是', '而且', '或者', '如果', '虽然', '即使',
    '可以', '需要', '应该', '必须', '可能', '已经', '正在', '将要',
    '进行', '完成', '实现', '使用', '包括', '通过', '关于', '根据',
    '之后', '之前', '之间', '以上', '以下', '当中', '其中', '其他',
    '现在', '今天', '昨天', '明天', '今年', '去年', '明年', '最近',
    '时候', '地方', '方面', '问题', '情况', '内容', '结果', '原因',
    '方法', '方式', '目的', '意义', '作用', '影响', '效果', '价值',
    '用户', '系统', '数据', '信息', '功能', '服务', '操作', '管理',
    '东西', '事情', '部分', '所有', '全部', '一些', '很多', '非常',
    '不是', '没有', '不要', '只是', '还有', '就是', '还有', '一下',
    '一直', '一起', '一点', '一些', '一样', '一般', '一定', '一样',
    
    # 常见动词（不应该作为实体）
    '开发', '测试', '验收', '反馈', '同步', '整理', '归档', '确认',
    '创建', '修改', '删除', '查询', '更新', '添加', '执行', '运行',
    '启动', '停止', '重启', '安装', '卸载', '配置', '部署', '发布',
    '提交', '推送', '拉取', '合并', '分支', '克隆', '检出', '切换',
    '发现', '识别', '提取', '分析', '评估', '检查', '验证', '审查',
    '设计', '实现', '优化', '重构', '维护', '迭代', '升级', '降级',
    '记录', '保存', '加载', '读取', '写入', '导入', '导出', '传输',
    '连接', '断开', '绑定', '解绑', '关联', '取消', '关闭', '打开',
    '学习', '研究', '探索', '尝试', '实践', '应用', '采用', '选择',
    '参与', '负责', '担任', '担任', '担任', '处理', '解决', '处理',
    '沟通', '协调', '组织', '安排', '指导', '协助', '支持', '帮助',
    '推进', '促进', '提升', '改善', '改进', '优化', '完善', '完善',
    
    # 英文停用词
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'must', 'shall', 'can',
    'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them',
    'and', 'or', 'but', 'if', 'then', 'else', 'when', 'where',
    'what', 'which', 'who', 'whom', 'how', 'why', 'for', 'to',
    'of', 'in', 'on', 'at', 'by', 'with', 'from', 'about',
    
    # 英文常见动词
    'develop', 'test', 'check', 'verify', 'validate', 'review', 'audit',
    'create', 'make', 'build', 'implement', 'deploy', 'release', 'publish',
    'update', 'modify', 'change', 'delete', 'remove', 'add', 'insert',
    'run', 'execute', 'start', 'stop', 'restart', 'install', 'setup', 'configure',
    'commit', 'push', 'pull', 'merge', 'branch', 'clone', 'checkout',
    'find', 'search', 'discover', 'detect', 'identify', 'analyze', 'evaluate',
    'design', 'optimize', 'refactor', 'maintain', 'iterate', 'upgrade', 'downgrade',
    'save', 'load', 'read', 'write', 'import', 'export', 'transfer',
    'connect', 'disconnect', 'bind', 'unbind', 'link', 'unlink', 'close', 'open',
    'learn', 'study', 'research', 'explore', 'try', 'practice', 'apply', 'use',
    'participate', 'handle', 'solve', 'process', 'communicate', 'coordinate',
    'organize', 'arrange', 'guide', 'assist', 'support', 'help',
    'promote', 'improve', 'enhance', 'perfect', 'complete', 'finish',
}

# 实体后缀词（表示专有名词的后缀）
ENTITY_SUFFIXES = {
    # 组织
    '公司', '集团', '企业', '机构', '组织', '协会', '联盟', '团队',
    # 技术产品
    '系统', '平台', '工具', '软件', '框架', '库', '插件', '扩展',
    '服务', '应用', '程序', '引擎', '协议', '接口', 'API', 'SDK',
    # 项目
    '项目', '产品', '版本', '功能', '模块', '组件',
    # 概念
    '模型', '算法', '技术', '方法', '理论', '规范', '标准',
    # 金融
    '银行', '基金', '股票', '证券', '保险',
    # 文档
    '文档', '手册', '指南', '教程', '报告',
    # 游戏
    '游戏', '服务器', '角色', '职业', '副本', '任务',
}

# 实体前缀词（表示专有名词的前缀）
ENTITY_PREFIXES = {
    '新', '旧', '大', '小', '主', '副', '总', '首', '上', '下',
    '前', '后', '左', '右', '高', '低', '快', '慢', '好', '坏',
    '智能', '自动', '人工', '深度', '机器', '数据', '云', '本地',
}

# 常见人名姓氏（用于识别人名）
COMMON_SURNAMES = {
    '王', '李', '张', '刘', '陈', '杨', '赵', '黄', '周', '吴',
    '徐', '孙', '胡', '朱', '高', '林', '何', '郭', '马', '罗',
    '梁', '宋', '郑', '谢', '韩', '唐', '冯', '于', '董', '萧',
    '程', '曹', '袁', '邓', '许', '傅', '沈', '曾', '彭', '吕',
    '苏', '卢', '蒋', '蔡', '贾', '丁', '魏', '薛', '叶', '阎',
}

# 技术术语白名单（这些词应该被识别为实体）
TECH_TERMS = {
    # 编程语言
    'Python', 'JavaScript', 'Java', 'Go', 'Rust', 'C++', 'TypeScript',
    'Ruby', 'PHP', 'Swift', 'Kotlin', 'Scala', 'Lua', 'Perl',
    # Node.js 系列
    'Node.js', 'node.js', 'Node', 'node', 'npm', 'yarn', 'pnpm',
    'Express', 'Koa', 'Next.js', 'Nuxt.js', 'Vue', 'React',
    # 框架和库
    'Angular', 'Django', 'Flask', 'FastAPI', 'Spring',
    'TensorFlow', 'PyTorch', 'Keras', 'NumPy', 'Pandas', 'Scikit-learn',
    # 工具
    'Git', 'Docker', 'Kubernetes', 'Jenkins', 'Nginx', 'Apache',
    'VSCode', 'Vim', 'Emacs', 'IntelliJ', 'PyCharm', 'VS Code',
    # 数据库
    'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'SQLite', 'Elasticsearch',
    'LanceDB', 'lancedb',
    # 云服务
    'AWS', 'Azure', 'GCP', 'Alibaba', 'Tencent',
    # AI 相关
    'GPT', 'BERT', 'Transformer', 'LLM', 'RAG', 'Embedding',
    'OpenAI', 'Anthropic', 'Claude', 'ChatGPT', 'Qwen', 'MiniMax',
    # 游戏相关
    'WoW', '魔兽世界', '暴雪', '网易', 'Steam',
    # 其他
    'API', 'REST', 'GraphQL', 'gRPC', 'HTTP', 'HTTPS', 'TCP', 'UDP',
    'JSON', 'XML', 'YAML', 'Markdown', 'SQL', 'NoSQL',
}

# 技术术语别名映射（小写 -> 标准名称）
TECH_TERM_ALIASES = {
    'nodejs': 'Node.js',
    'node': 'Node.js',
    'js': 'JavaScript',
    'ts': 'TypeScript',
    'py': 'Python',
    'vscode': 'VS Code',
    'vs_code': 'VS Code',
}

# 自定义词典（添加领域特定词汇）
CUSTOM_DICT = {
    # 项目相关
    'Memory Bank': 100,
    'OpenClaw': 100,
    '毒药小队': 100,
    'myclaw': 100,
    'xiaoP': 100,
    # 技术术语
    '向量数据库': 50,
    '全文搜索': 50,
    '嵌入模型': 50,
    '实体识别': 50,
    '命名实体': 50,
    # 游戏术语
    '艾泽拉斯': 100,
    '血精灵': 100,
    '永歌森林': 100,
    '至暗之夜': 100,
}


# ==================== 初始化 ====================

def _init_jieba():
    """初始化 jieba，添加自定义词典"""
    for word, freq in CUSTOM_DICT.items():
        jieba.add_word(word, freq)
    # 也添加技术术语
    for term in TECH_TERMS:
        jieba.add_word(term, 200)
    
    # 从 LanceDB 同步实体词典
    _sync_jieba_from_lancedb()


def _sync_jieba_from_lancedb():
    """从 LanceDB 同步实体到 jieba 词典"""
    try:
        import lancedb
        from pathlib import Path
        
        db_path = Path.home() / ".openclaw" / "workspace" / ".memory" / "lancedb"
        if not db_path.exists():
            return
        
        db = lancedb.connect(str(db_path))
        
        try:
            # 读取 entities 表
            table = db.open_table("entities")
            results = table.to_list()
            
            # 提取实体名称并加入 jieba
            count = 0
            for row in results:
                name = row.get("name", "")
                if name and len(name) >= 2:
                    jieba.add_word(name, freq=5)
                    count += 1
                
                # 也处理别名
                aliases = row.get("aliases", [])
                if aliases:
                    for alias in aliases:
                        if alias and len(alias) >= 2:
                            jieba.add_word(alias, freq=5)
                            count += 1
            
            if count > 0:
                print(f"[NER] 从 LanceDB 同步了 {count} 个实体到 jieba 词典")
                
        except Exception as e:
            # 表可能不存在
            pass
            
    except Exception as e:
        # 忽略同步错误，不影响主流程
        pass


_init_jieba()


# ==================== 核心函数 ====================

def extract_entities(
    content: str,
    use_ner: bool = True,
    use_suffix: bool = True,
    use_prefix: bool = False,  # 默认关闭前缀匹配（太激进）
    use_tech_terms: bool = True,
    min_length: int = 2,
    max_length: int = 20,
) -> List[str]:
    """
    从内容中提取实体
    
    Args:
        content: 文本内容
        use_ner: 使用 jieba 词性标注提取人名、地名、组织名
        use_suffix: 使用后缀规则提取
        use_prefix: 使用前缀规则提取（可能误判）
        use_tech_terms: 匹配技术术语白名单
        min_length: 实体最小长度
        max_length: 实体最大长度
        
    Returns:
        去重后的实体列表
    """
    entities = set()
    
    # 1. 技术术语匹配（优先级最高）
    if use_tech_terms:
        entities.update(_extract_tech_terms(content))
    
    # 2. jieba 词性标注 NER
    if use_ner:
        entities.update(_extract_with_posseg(content))
    
    # 3. 后缀规则
    if use_suffix:
        entities.update(_extract_by_suffix(content))
    
    # 4. 前缀规则（谨慎使用）
    if use_prefix:
        entities.update(_extract_by_prefix(content))
    
    # 5. 人名识别（姓氏 + 名字）
    entities.update(_extract_chinese_names(content))
    
    # 过滤和清理
    filtered = _filter_entities(entities, min_length, max_length)
    
    return list(filtered)


def _extract_tech_terms(content: str) -> Set[str]:
    """提取技术术语（精确匹配，统一大小写）"""
    found = set()
    content_lower = content.lower()
    
    for term in TECH_TERMS:
        # 大小写不敏感匹配（除了全大写的缩写）
        if term.isupper():
            if term in content:
                found.add(term)
        elif term.lower() in content_lower:
            # 使用标准名称（从别名映射）
            standard_name = TECH_TERM_ALIASES.get(term.lower(), term)
            found.add(standard_name)
    
    # 检查别名
    for alias, standard in TECH_TERM_ALIASES.items():
        if alias in content_lower:
            found.add(standard)
    
    return found


def _extract_with_posseg(content: str) -> Set[str]:
    """
    使用 jieba 词性标注提取实体
    
    词性标注说明：
    - nr: 人名
    - ns: 地名
    - nt: 机构团体
    - nz: 其他专名
    - ng: 名词语素（可能是专有名词的一部分）
    - n: 名词（需要过滤）
    - vn: 动名词（需要过滤）
    - v: 动词（排除）
    - a: 形容词（排除）
    """
    entities = set()
    
    # 词性标注
    words = pseg.cut(content)
    
    for word, flag in words:
        # 跳过停用词
        if word in STOP_WORDS:
            continue
        
        # 跳过动词和形容词
        if flag in ('v', 'a', 'ad', 'an', 'vd', 'vn', 'ag'):
            continue
        
        # 跳过太短的词（小于2个字符）
        if len(word) < 2:
            continue
        
        # 人名、地名、机构名、其他专名
        if flag in ('nr', 'ns', 'nt', 'nz', 'ng'):
            entities.add(word)
        
        # 名词（需要额外判断）
        elif flag == 'n':
            # 检查是否包含专有名词特征
            if _is_likely_entity(word):
                entities.add(word)
    
    return entities


def _extract_by_suffix(content: str) -> Set[str]:
    """根据后缀词提取实体"""
    entities = set()
    
    for suffix in ENTITY_SUFFIXES:
        # 匹配：1-6 个中文字符 + 后缀
        pattern = rf'[\u4e00-\u9fa5]{{1,6}}{suffix}'
        matches = re.findall(pattern, content)
        for match in matches:
            if match not in STOP_WORDS:
                entities.add(match)
    
    return entities


def _extract_by_prefix(content: str) -> Set[str]:
    """根据前缀词提取实体（谨慎使用）"""
    entities = set()
    
    for prefix in ENTITY_PREFIXES:
        # 匹配：前缀 + 1-5 个中文字符
        pattern = rf'{prefix}[\u4e00-\u9fa5]{{1,5}}'
        matches = re.findall(pattern, content)
        for match in matches:
            if match not in STOP_WORDS and len(match) > 2:
                entities.add(match)
    
    return entities


def _extract_chinese_names(content: str) -> Set[str]:
    """
    识别中文人名
    
    规则：常见姓氏 + 1-2 个字
    例如：张三、李四、王小明
    """
    entities = set()
    
    for surname in COMMON_SURNAMES:
        # 姓氏 + 1-2 个中文字符
        pattern = rf'{surname}[\u4e00-\u9fa5]{{1,2}}'
        matches = re.findall(pattern, content)
        for match in matches:
            # 确保不是常用词
            if match not in STOP_WORDS:
                entities.add(match)
    
    return entities


def _is_likely_entity(word: str) -> bool:
    """
    判断一个词是否可能是实体
    
    启发式规则：
    1. 不在停用词表中
    2. 不是纯动词/形容词
    3. 包含大写字母（英文专有名词）
    4. 包含数字（可能是版本号、产品名）
    """
    if word in STOP_WORDS:
        return False
    
    # 包含大写字母
    if any(c.isupper() for c in word):
        return True
    
    # 包含数字
    if any(c.isdigit() for c in word):
        return True
    
    # 中文词，长度 2-6
    if re.match(r'^[\u4e00-\u9fa5]{2,6}$', word):
        # 检查是否以实体后缀结尾
        for suffix in ENTITY_SUFFIXES:
            if word.endswith(suffix):
                return True
    
    return False


def _filter_entities(
    entities: Set[str],
    min_length: int,
    max_length: int
) -> Set[str]:
    """
    过滤实体
    
    - 长度限制
    - 去除停用词
    - 去除纯数字
    - 去除单字
    """
    filtered = set()
    
    for entity in entities:
        # 长度检查
        if not (min_length <= len(entity) <= max_length):
            continue
        
        # 停用词检查
        if entity.lower() in STOP_WORDS or entity in STOP_WORDS:
            continue
        
        # 纯数字检查
        if entity.isdigit():
            continue
        
        # 纯标点检查
        if re.match(r'^[\W_]+$', entity):
            continue
        
        filtered.add(entity)
    
    return filtered


# ==================== 辅助函数 ====================

def slugify(name: str) -> str:
    """
    将实体名称转换为 slug（用于唯一标识）
    
    Args:
        name: 实体名称
        
    Returns:
        slug 字符串
    """
    import hashlib
    
    # 转小写，去空格
    slug = name.lower().strip()
    
    # 如果是纯英文/数字，直接返回
    if re.match(r'^[a-z0-9_-]+$', slug):
        return slug
    
    # 包含中文，使用 hash
    hash_val = hashlib.md5(name.encode('utf-8')).hexdigest()[:8]
    return f"entity_{hash_val}"


def extract_entities_with_type(content: str) -> List[Tuple[str, str]]:
    """
    提取实体并推断类型
    
    Returns:
        [(entity_name, entity_type), ...]
    """
    from .entity_type_cache import EntityTypeInferencer
    
    entities = extract_entities(content)
    result = []
    
    # 延迟导入避免循环依赖
    try:
        from .database import get_db
        db = get_db()
        inferencer = EntityTypeInferencer(db)
        
        for entity in entities:
            entity_type, _, _ = inferencer.infer(entity)
            result.append((entity, entity_type))
    except Exception as e:
        # 推断失败，默认 PERSON
        logger.warning(f"Entity type inference failed: {e}, using PERSON as fallback")
        for entity in entities:
            result.append((entity, 'PERSON'))
    
    return result


# ==================== 测试 ====================

if __name__ == '__main__':
    print("=" * 60)
    print("NER 实体识别测试")
    print("=" * 60)
    
    test_cases = [
        "张三安装了 VSCode 和 Docker，用于开发 Memory Bank 项目",
        "李四使用 Python 和 Flask 搭建了一个 Web 服务",
        "王五在 北京 的腾讯公司工作，主要研究深度学习和 Transformer",
        "安装了 Claude API，准备接入 OpenClaw 系统",
        "魔兽世界的血精灵种族来自永歌森林",
        "今天学习了 GPT 和 BERT 的区别",
        "这是一个普通的句子，没有专有名词",
    ]
    
    for text in test_cases:
        print(f"\n📝 {text}")
        entities = extract_entities(text)
        print(f"   提取: {entities}")
    
    print("\n" + "=" * 60)
