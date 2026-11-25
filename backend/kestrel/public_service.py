"""Future reviewed Windows service entrypoint; never changes the LOCAL launcher."""


def main():
    from kestrel.main import create_app
    import uvicorn
    app=create_app()
    if not app.state.deployment.public:raise RuntimeError('Explicit owner-approved PUBLIC_DEMO configuration required')
    uvicorn.run(app,host='127.0.0.1',port=8000,workers=1,proxy_headers=False,forwarded_allow_ips='',
        access_log=False,server_header=False,ws='none',http='h11',limit_concurrency=64,
        timeout_keep_alive=5,h11_max_incomplete_event_size=16384)


if __name__=='__main__':main()
