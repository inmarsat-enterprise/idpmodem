from idpmodem.s_registers import SRegister, SRegisters, REGISTER_DEFINITIONS

def test_s_reg():
    registers = SRegisters()
    assert len(registers) == len(REGISTER_DEFINITIONS)
    for name, reg in registers.items():
        assert isinstance(reg, SRegister)
        assert reg.name == name
        assert isinstance(reg.default, int)
        assert isinstance(reg.value, int)
        assert isinstance(reg.read_only, bool)
        assert isinstance(reg.min_max, range)
        assert isinstance(reg.min, int)
        assert isinstance(reg.max, int)
        assert isinstance(reg.description, str) or reg.description is None
        assert isinstance(reg.note, str) or reg.note is None
