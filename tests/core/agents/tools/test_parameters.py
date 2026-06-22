"""Tests for the parameters module."""


async def test_get_org_parameters_default(call):
    """Getting parameters before the org is set up returns an empty `parameters` dict."""
    result = await call('get_org_parameters')
    assert result == {'parameters': {}}


async def test_set_then_get_roundtrips(call):
    """Setting one parameter, then reading back, returns the new state with that parameter."""
    set_state = await call('set_org_parameter', name='domain_focus', value='AI')
    assert set_state == {'parameters': {'domain_focus': 'AI'}}
    get_state = await call('get_org_parameters')
    assert get_state == set_state


async def test_reset_clears_parameters(call):
    """After reset, parameters are empty and a follow-up read confirms it."""
    await call('set_org_parameter', name='min_sources', value=5)
    await call('reset_org_parameters')
    result = await call('get_org_parameters')
    assert result == {'parameters': {}}
