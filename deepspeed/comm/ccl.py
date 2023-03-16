'''
Copyright 2021 The Microsoft DeepSpeed Team
'''

from deepspeed.ops.comm.ccl import build_ccl_op

from .reduce_op import ReduceOp
from .torch import TorchBackend
import torch


class CCLBackend(TorchBackend):
    def __init__(self,
                 name='ccl',
                 rank=-1,
                 world_size=-1,
                 mpu=None,
                 timeout=None,
                 init_method=None):
        super(CCLBackend,
              self).__init__(backend='ccl',
                             name='torch',
                             rank=rank,
                             world_size=world_size,
                             timeout=timeout,
                             init_method=init_method)
        self.name = 'ccl'
        self.ccl_comm_op = build_ccl_op()
        size = self.get_world_size()
        rank = self.get_rank()
        if rank == 0:
            main_kvs = self.ccl_comm_op.create_main_kvs()
            main_kvs = torch.tensor(main_kvs).to(torch.uint8)
        else:
            main_kvs = torch.zeros((256), dtype=torch.uint8)
        super(CCLBackend, self).broadcast(main_kvs, 0)
        self.ccl_comm_op.initialize(size, rank, main_kvs)

    def broadcast(self, tensor, src, group=None, async_op=False):
        self.ccl_comm_op.broadcast(tensor, src, group, async_op)

    def all_reduce(self, tensor, op=ReduceOp.SUM, group=None, async_op=False):
        self.ccl_comm_op.all_reduce(tensor, op, group, async_op)

    def barrier(self, group=None, async_op=False):
        self.ccl_comm_op.barrier(group, async_op)
