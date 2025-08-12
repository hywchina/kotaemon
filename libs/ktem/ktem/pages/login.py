import hashlib

import gradio as gr
from ktem.app import BasePage
from ktem.db.models import User, engine
from ktem.pages.resources.user import create_user
from sqlmodel import Session, select

fetch_creds = """
function() {
    const username = getStorage('username', '')
    const password = getStorage('password', '')
    return [username, password, null];
}
"""

signin_js = """
function(usn, pwd) {
    setStorage('username', usn);
    setStorage('password', pwd);
    return [usn, pwd];
}
"""


class LoginPage(BasePage):

    public_events = ["onSignIn"]

    def __init__(self, app):
        self._app = app
        self.on_building_ui()

    def on_building_ui(self):
        gr.Markdown(f"# 欢迎使用{self._app.app_name}！")  # translate Welcome to... --》欢迎使用...！
        self.usn = gr.Textbox(label="用户名", visible=False)  # translate Username --》用户名
        self.pwd = gr.Textbox(label="密码", type="password", visible=False)  # translate Password --》密码
        self.btn_login = gr.Button("登录", visible=False)  # translate Login --》登录

    def on_register_events(self):
        onSignIn = gr.on(
            triggers=[self.btn_login.click, self.pwd.submit],
            fn=self.login,
            inputs=[self.usn, self.pwd],
            outputs=[self._app.user_id, self.usn, self.pwd],
            show_progress="hidden",
            js=signin_js,
        ).then(
            self.toggle_login_visibility,
            inputs=[self._app.user_id],
            outputs=[self.usn, self.pwd, self.btn_login],
        )
        for event in self._app.get_event("onSignIn"):
            onSignIn = onSignIn.success(**event)

    def toggle_login_visibility(self, user_id):
        return (
            gr.update(visible=user_id is None),
            gr.update(visible=user_id is None),
            gr.update(visible=user_id is None),
        )

    def _on_app_created(self):
        onSignIn = self._app.app.load(
            self.login,
            inputs=[self.usn, self.pwd],
            outputs=[self._app.user_id, self.usn, self.pwd],
            show_progress="hidden",
            js=fetch_creds,
        ).then(
            self.toggle_login_visibility,
            inputs=[self._app.user_id],
            outputs=[self.usn, self.pwd, self.btn_login],
        )
        for event in self._app.get_event("onSignIn"):
            onSignIn = onSignIn.success(**event)

    def on_subscribe_public_events(self):
        self._app.subscribe_event(
            name="onSignOut",
            definition={
                "fn": self.toggle_login_visibility,
                "inputs": [self._app.user_id],
                "outputs": [self.usn, self.pwd, self.btn_login],
                "show_progress": "hidden",
            },
        )

    def login(self, usn, pwd, request: gr.Request):
        try:
            import gradiologin as grlogin

            user = grlogin.get_user(request)
        except (ImportError, AssertionError):
            user = None

        if user:
            user_id = user["sub"]
            with Session(engine) as session:
                stmt = select(User).where(
                    User.id == user_id,
                )
                result = session.exec(stmt).all()

            if result:
                print("现有用户:", user)  # translate Existing user --》现有用户
                return user_id, "", ""
            else:
                print("创建新用户:", user)  # translate Creating new user --》创建新用户
                create_user(
                    usn=user["email"],
                    pwd="",
                    user_id=user_id,
                    is_admin=False,
                )
                return user_id, "", ""
        else:
            if not usn or not pwd:
                return None, usn, pwd

            hashed_password = hashlib.sha256(pwd.encode()).hexdigest()
            with Session(engine) as session:
                stmt = select(User).where(
                    User.username_lower == usn.lower().strip(),
                    User.password == hashed_password,
                )
                result = session.exec(stmt).all()
                if result:
                    return result[0].id, "", ""

                gr.Warning("用户名或密码无效")  # translate Invalid username or password --》用户名或密码无效
                return None, usn, pwd
