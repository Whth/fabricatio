import pytest

from fabricatio.models.action import WorkFlow
from fabricatio.models.role import Role


class TestWorkflow(WorkFlow):
    async def execute(self, *args, **kwargs):
        return "executed"


@pytest.mark.asyncio
async def test_role_act():
    role = Role(workflows=[TestWorkflow()])
    await role.act()
