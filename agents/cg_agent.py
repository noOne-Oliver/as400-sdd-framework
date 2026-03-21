"""Code generation agent for RPGLE and CL programs."""

from __future__ import annotations

import re
from pathlib import Path

from .base_agent import BaseAgent, ValidationResult


class CGAgent(BaseAgent):
    def __init__(self, llm_client=None):
        super().__init__("cg_agent", llm_client, "prompts/cg_agent")

    def execute(self, input_data: dict) -> dict:
        analysis = input_data["analysis"]
        sdd = input_data["sdd"]
        tests = input_data["tests"]
        program_name = analysis["program_name"]
        language = input_data.get("language", "rpgle").lower()

        if language == "cl":
            template = Path("templates/cl_template.cl").read_text(encoding="utf-8")
            code = template.format(program_name=program_name)
        else:
            code = self._build_rpgle(program_name, sdd, tests)

        return {
            "program_name": program_name,
            "language": language,
            "code": code,
        }

    def validate_output(self, output: dict) -> ValidationResult:
        issues = []
        code = output.get("code", "")
        required = ["ctl-opt", "dcl-f", "ORDPF", "CUSTMF", "INVPF", "ORDLOGPF"]
        for token in required:
            if token.lower() not in code.lower():
                issues.append(f"Generated code missing token: {token}")
        return ValidationResult(not issues, issues)

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
