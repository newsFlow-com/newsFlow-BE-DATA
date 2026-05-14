from datasketch import MinHash, MinHashLSH

# 유사도 임계값 (0.8 = 80% 이상 유사하면 중복으로 판단)
THRESHOLD = 0.8


def get_minhash(text: str, num_perm: int = 128) -> MinHash:
    """텍스트를 MinHash로 변환"""
    m = MinHash(num_perm=num_perm)
    for word in text.split():
        m.update(word.encode("utf-8"))
    return m


def is_duplicate(new_text: str, lsh: MinHashLSH) -> bool:
    """LSH를 이용해 중복 여부 판단"""
    m = get_minhash(new_text)
    result = lsh.query(m)
    return len(result) > 0