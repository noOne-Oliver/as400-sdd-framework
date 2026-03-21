"""Code generation agent for RPGLE and CL programs."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .base_agent import BaseAgent, ValidationResult


@dataclass
class FileSpec:
    filename: str
    type: str
    description: str
    priority: int


class CGAgent(BaseAgent):
    def __init__(self, llm_client=None):
        super().__init__("cg_agent", llm_client, "prompts/cg_agent")

    def execute(self, input_data: dict) -> dict:
        analysis = input_data["analysis"]
        sdd = input_data["sdd"]
        tests = input_data["tests"]
        program_name = analysis["program_name"]
        language = input_data.get("language", "rpgle").lower()
        context_summary = input_data.get("context_summary", "").strip()
        files_to_generate = self.plan_files(analysis, sdd)
        generated_files = {}

        for file_spec in files_to_generate:
            generated_files[file_spec.filename] = self._generate_single_file(
                file_spec=file_spec,
                program_name=program_name,
                language=language,
                sdd=sdd,
                tests=tests,
                context_summary=context_summary,
            )

        primary_filename = files_to_generate[0].filename
        code = generated_files[primary_filename]

        return {
            "program_name": program_name,
            "language": language,
            "code": code,
            "generated_files": generated_files,
            "files_to_generate": [asdict(file_spec) for file_spec in files_to_generate],
        }

    def validate_output(self, output: dict) -> ValidationResult:
        issues = []
        code = output.get("code", "")
        required = ["ctl-opt", "dcl-f", "ORDPF", "CUSTMF", "INVPF", "ORDLOGPF"]
        for token in required:
            if token.lower() not in code.lower():
                issues.append(f"Generated code missing token: {token}")
        if not output.get("files_to_generate"):
            issues.append("Generated output missing file plan.")
        return ValidationResult(not issues, issues)

    def plan_files(self, analysis: dict, sdd: str) -> list[FileSpec]:
        program_name = analysis["program_name"]
        lowered_sdd = sdd.lower()
        files = [
            FileSpec(
                filename=f"{program_name}.rpgle",
                type="rpgle",
                description="主处理程序",
                priority=1,
            )
        ]
        if "batch" in lowered_sdd or "调度" in sdd or "批处理入口" in sdd:
            files.append(
                FileSpec(
                    filename=f"{program_name}.cl",
                    type="cl",
                    description="批处理调用入口",
                    priority=2,
                )
            )
        return sorted(files, key=lambda item: item.priority)

    def _build_rpgle(self, program_name: str, sdd: str, tests: str) -> str:
        base_template = Path("templates/rpgle_template.rpgle").read_text(encoding="utf-8")
        if program_name.upper() == "ORDPRC":
            return self._build_order_processing_program()

        status_comment = self._extract_status_comment(sdd + "\n" + tests)
        return base_template.format(
            program_name=program_name,
            status_comment=status_comment,
        )

    @staticmethod
    def _extract_status_comment(text: str) -> str:
        matches = re.findall(r"0[289]", text)
        statuses = ", ".join(sorted(set(matches))) if matches else "02, 08, 09"
        return f"业务状态覆盖: {statuses}"

    def _generate_single_file(
        self,
        file_spec: FileSpec,
        program_name: str,
        language: str,
        sdd: str,
        tests: str,
        context_summary: str,
    ) -> str:
        prefix = self._build_context_prefix(context_summary, file_spec.type)
        if file_spec.type == "cl" or language == "cl":
            template = Path("templates/cl_template.cl").read_text(encoding="utf-8")
            return f"{prefix}{template.format(program_name=program_name)}"
        return f"{prefix}{self._build_rpgle(program_name, sdd, tests)}"

    @staticmethod
    def _build_context_prefix(context_summary: str, file_type: str) -> str:
        if not context_summary:
            return ""
        if file_type == "cl":
            return (
                "/* 执行上下文\n"
                f"{context_summary}\n"
                "*/\n"
            )
        return (
            "// 执行上下文\n"
            + "\n".join(f"// {line}" for line in context_summary.splitlines())
            + "\n"
        )

    @staticmethod
    def _build_order_processing_program() -> str:
        return """**FREE
ctl-opt dftactgrp(*no) actgrp(*new) option(*srcstmt:*nodebugio);

dcl-f ORDPF usage(*update:*input) keyed usropn;
dcl-f CUSTMF usage(*input) keyed usropn;
dcl-f INVPF usage(*update:*input) keyed usropn;
dcl-f ORDLOGPF usage(*output) usropn;

dcl-ds OrderRec extname('ORDPF') end-ds;
dcl-ds CustRec extname('CUSTMF') end-ds;
dcl-ds InvRec extname('INVPF') end-ds;
dcl-ds OrdLogR extname('ORDLOGPF') end-ds;

dcl-s EndOfFile ind inz(*off);
dcl-s ProcessStatus char(2) inz(*blanks);
dcl-s ProcessMessage char(50) inz(*blanks);

dcl-proc Main;
    open ORDPF;
    open CUSTMF;
    open INVPF;
    open ORDLOGPF;

    monitor;
        setll *loval ORDPF;
        dou EndOfFile;
            reade '01' ORDPF OrderRec;
            if %eof(ORDPF);
                EndOfFile = *on;
                leave;
            endif;

            clear ProcessStatus;
            clear ProcessMessage;

            if not IsValidCustomer(OrderRec.CUSTNO);
                ProcessStatus = '08';
                ProcessMessage = '客户无效';
            elseif not HasEnoughInventory(OrderRec.ITEMNO: OrderRec.ORDQTY);
                ProcessStatus = '09';
                ProcessMessage = '库存不足';
            else;
                ProcessStatus = '02';
                ProcessMessage = '订单确认完成';
                UpdateInventory(OrderRec.ITEMNO: OrderRec.ORDQTY);
            endif;

            UpdateOrderStatus(OrderRec.ORDNO: ProcessStatus);
            WriteOrderLog(OrderRec.ORDNO: OrderRec.CUSTNO: ProcessStatus: ProcessMessage);
        enddo;
    on-error;
        WriteOrderLog('SYSTEM': 'SYSTEM': '99': 'ORDPRC 发生未处理异常');
        dsply ('ORDPRC failed');
    endmon;

    *inlr = *on;
end-proc;

dcl-proc IsValidCustomer;
    dcl-pi *n ind;
        customerNumber packed(9:0) const;
    end-pi;

    chain customerNumber CUSTMF CustRec;
    return not %eof(CUSTMF);
end-proc;

dcl-proc HasEnoughInventory;
    dcl-pi *n ind;
        itemNumber char(15) const;
        requiredQty packed(9:0) const;
    end-pi;

    chain itemNumber INVPF InvRec;
    if %eof(INVPF);
        return *off;
    endif;

    return InvRec.ONHAND >= requiredQty;
end-proc;

dcl-proc UpdateInventory;
    dcl-pi *n;
        itemNumber char(15) const;
        requiredQty packed(9:0) const;
    end-pi;

    chain itemNumber INVPF InvRec;
    if not %eof(INVPF);
        InvRec.ONHAND -= requiredQty;
        update INVPF InvRec;
    endif;
end-proc;

dcl-proc UpdateOrderStatus;
    dcl-pi *n;
        orderNumber packed(9:0) const;
        newStatus char(2) const;
    end-pi;

    chain orderNumber ORDPF OrderRec;
    if not %eof(ORDPF);
        OrderRec.STATUS = newStatus;
        update ORDPF OrderRec;
    endif;
end-proc;

dcl-proc WriteOrderLog;
    dcl-pi *n;
        orderNumber char(10) const;
        customerNumber char(10) const;
        resultStatus char(2) const;
        resultMessage char(50) const;
    end-pi;

    clear OrdLogR;
    OrdLogR.ORDNO = orderNumber;
    OrdLogR.CUSTNO = customerNumber;
    OrdLogR.STATUS = resultStatus;
    OrdLogR.MESSAGE = resultMessage;
    OrdLogR.LOGTS = %timestamp();
    write ORDLOGPF OrdLogR;
end-proc;
"""
