# FastAPI Gatekeeper

An OIDC proxy designed to sit in front of insecure services, intercept requests, authenticate with a third party IdP (e.g. Dex) and then authorise them.

## Quick Start

Use the provided `docker-compose.yaml`. This will deploy a couple of test services.

```zsh
docker compose up
```

Now run the proxy with the sample environment variables set.

```zsh
GATEKEEPER_ENV=sample src/run.py
```

### Authentication

Navigate to a protected route. You'll be prompted to login with credentials before you're able to access that resource.

- [localhost:8000/proxy-endpoint/super-secret](http://localhost:8000/proxy-endpoint/super-secret) will give you transparently proxied information from a remote service.
- [localhost:8000/about/me](http://localhost:8000/about/me) will give you information about the currently logged in user.

![login options](docs/img/dex-login-options.png)

- There is an "Email" login available with the credentials `admin@example.com` and `password`.
- Choose `Planet Express` to login with LDAP credentials for that organisation. The ldap server uses [docker-test-openldap](https://github.com/rroemhild/docker-test-openldap) with an existing pre-populated list of users and groups. For example, `professor@planetexpress.com` with password `professor`.

**Any logged in user can access these routes currently.**

### Authorisation

The [admins-only](http://localhost:8000/admins-only) endpoint requires that an individual is in the `admin_staff` group.

```py
@app.get("/admins-only")
    async def admin_endpoint(
        user: dict = Depends(get_current_user_group("admin_staff")),
    ):
        return {"message": "Welcome, admin!"}

    return app
```

If you attempt to navigate here as a user such as `bender@planetexpress.com` password `bender` you'll be presented with a `403` error.

> {"message":"Unauthorised. You shouldn't be here."}

Navigating with this user to [/about/me](http://localhost:8000/about/me) indicates this is because they're part of only the `ship_crew` group.
