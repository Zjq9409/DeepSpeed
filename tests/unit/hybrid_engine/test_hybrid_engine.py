# Copyright (c) Microsoft Corporation.
# SPDX-License-Identifier: Apache-2.0

# DeepSpeed Team

import os
import torch
import pytest
import deepspeed
from deepspeed.ops.op_builder import OpBuilder
from unit.common import DistributedTest

from transformers import (AutoConfig, AutoTokenizer, AutoModelForCausalLM)

pytest.skip("skip test for now, will fix in follow-up PR", allow_module_level=True)

rocm_version = OpBuilder.installed_rocm_version()
if rocm_version != (0, 0):
    pytest.skip("skip inference tests on rocm for now", allow_module_level=True)


@pytest.mark.inference
@pytest.mark.parametrize("batch_size", [1, 2], ids=["bsz=1", "bsz=2"])
@pytest.mark.parametrize("model_name", ["EleutherAI/gpt-neo-1.3B", "facebook/opt-1.3b"])
class TestHybridEngineTextGen(DistributedTest):
    world_size = 1

    def _generate(self, model, tokenizer, prompt):
        local_rank = int(os.getenv("LOCAL_RANK", "0"))
        tokens = tokenizer.batch_encode_plus(prompt, return_tensors="pt", padding=True)
        for t in tokens:
            if torch.is_tensor(tokens[t]):
                tokens[t] = tokens[t].to(f'cuda:{local_rank}')
        output = model.generate(**tokens, do_sample=False, max_length=100)
        outputs = tokenizer.batch_decode(output, skip_special_tokens=True)
        return outputs

    def test(self, batch_size, model_name):
        local_rank = int(os.getenv("LOCAL_RANK", "0"))

        model_config = AutoConfig.from_pretrained(model_name)
        model_config.dropout = 0.0
        model = AutoModelForCausalLM.from_pretrained(model_name, config=model_config)
        model = model.to(f'cuda:{local_rank}')
        model = model.half()

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        tokenizer.pad_token = tokenizer.eos_token

        if batch_size == 1:
            prompt = ["Microsoft is in Washington"]
        elif batch_size == 2:
            prompt = ["DeepSpeed is", "Microsoft is in Washington"]
        else:
            raise NotImplementedError(f"batch_size {batch_size} not implemented")

        base_out = self._generate(model, tokenizer, prompt)

        ds_config = {"train_batch_size": 1, "fp16": {"enabled": True}, "hybrid_engine": {"enabled": True}}
        model, *_ = deepspeed.initialize(model=model, config=ds_config)

        model.eval()
        ds1_out = self._generate(model, tokenizer, prompt)
        assert base_out == ds1_out, f"base_out: {base_out}, ds1_out: {ds1_out}"

        model.train()
        model.eval()
        ds2_out = self._generate(model, tokenizer, prompt)
        assert base_out == ds2_out
