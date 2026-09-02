def test_dashboard_observability_endpoint_is_documented():
    import web_server

    assert callable(web_server.ISPHandler.get_observability)
    assert web_server.ISPHandler.get_observability.__doc__
