from types import ModuleType
from fabricatio_core.decorators import use_temp_module


def test_process_data():
    module1 = ModuleType('mod1')
    module2 = ModuleType('mod2')

    @use_temp_module([module1, module2])
    def process_data():
        import sys
        return sys.modules.get('mod1'), sys.modules.get('mod2')

    result_mod1, result_mod2 = process_data()
    assert result_mod1 is module1
    assert result_mod2 is module2