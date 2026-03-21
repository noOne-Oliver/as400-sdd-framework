from core.judge import Judge


def test_judge_spec_passes():
    judge = Judge()
    sdd = """
    # 软件设计说明书
    程序: ORDPRC
    业务规则
    处理流程
    错误处理
    测试
    ORDPF
    状态
    """
    result = judge.evaluate_spec(sdd)
    assert result.score >= 1
