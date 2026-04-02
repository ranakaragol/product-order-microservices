from fastapi import FastAPI


def register_gateway_routes(
    app: FastAPI,
    *,
    read_root_handler,
    metrics_handler,
    proxy_auth_handler,
    proxy_products_handler,
    proxy_products_root_handler,
    proxy_orders_handler,
    proxy_orders_root_handler,
    auth_proxy_methods,
) -> None:
    app.add_api_route("/", read_root_handler, methods=["GET"])
    app.add_api_route("/metrics", metrics_handler, methods=["GET"], include_in_schema=False)
    app.add_api_route("/auth/{path:path}", proxy_auth_handler, methods=auth_proxy_methods)
    app.add_api_route("/products/{path:path}", proxy_products_handler, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    app.add_api_route("/products", proxy_products_root_handler, methods=["GET", "POST"])
    app.add_api_route("/orders/{path:path}", proxy_orders_handler, methods=["GET", "POST", "PATCH", "DELETE"])
    app.add_api_route("/orders", proxy_orders_root_handler, methods=["GET", "POST"])
