from domain.case_models import CasePoint, CaseResult


def test_case_summarizer_port_is_runtime_checkable():
    from domain.case_models import CaseContext
    from domain.case_models import CaseResult as _CaseResult
    from domain.ports import CaseSummarizerPort

    class _Fake:
        def summarize_case(self, ctx: CaseContext) -> _CaseResult:
            return _CaseResult((), (), True)

    assert isinstance(_Fake(), CaseSummarizerPort)


def test_case_result_holds_both_sides_and_gap_flag():
    favor = (CasePoint(text="Beat EPS 3 of 4 quarters", source_tag="reported"),)
    watch = (CasePoint(text="Below 200-day trend", source_tag="technical"),)
    res = CaseResult(in_favor=favor, to_watch=watch, data_gap=False)
    assert res.in_favor[0].source_tag == "reported"
    assert res.to_watch[0].text == "Below 200-day trend"
    assert res.data_gap is False


def test_case_result_gap_default():
    assert CaseResult(in_favor=(), to_watch=(), data_gap=True).data_gap is True
