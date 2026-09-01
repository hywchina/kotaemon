import logging

import gradio as gr
from ktem.app import BasePage
from ktem.db.models import User, engine
from ktem.pages.resources.user import create_user
from ktem.utils.passwords import verify_and_upgrade
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

fetch_creds = """
function() {
    let username = '';
    try {
        username = localStorage.getItem('username') || '';
        localStorage.removeItem('password');
    } catch (error) {
        console.warn('Unable to read saved login name', error);
    }
    return [username, '', null];
}
"""

signin_js = """
function(usn, pwd) {
    try {
        localStorage.setItem('username', usn);
        localStorage.removeItem('password');
    } catch (error) {
        console.warn('Unable to save login name', error);
    }
    return [usn, pwd];
}
"""


class LoginPage(BasePage):
    public_events = ["onSignIn"]

    def __init__(self, app):
        self._app = app
        self.on_building_ui()

    def on_building_ui(self):
        gr.Markdown(
            f"# 欢迎使用{self._app.app_name}！"
        )  # translate Welcome to... --》欢迎使用...！
        # The login tab is itself hidden after authentication, so keeping its
        # controls initially visible avoids an unusable blank page if a separate
        # optional UI enhancement fails during the first browser render.
        self.usn = gr.Textbox(label="用户名")  # translate Username --》用户名
        self.pwd = gr.Textbox(
            label="密码", type="password"
        )  # translate Password --》密码
        self.btn_login = gr.Button("登录")  # translate Login --》登录

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
                logger.info("Existing SSO user authenticated")
                return user_id, "", ""
            else:
                logger.info("Creating a local account for a new SSO user")
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

            with Session(engine) as session:
                stmt = select(User).where(
                    User.username_lower == usn.lower().strip(),
                )
                user = session.exec(stmt).one_or_none()
                if user:
                    valid, upgraded_hash = verify_and_upgrade(pwd, user.password)
                    if valid:
                        if upgraded_hash:
                            user.password = upgraded_hash
                            session.add(user)
                            session.commit()
                        return user.id, "", ""

                gr.Warning(
                    "用户名或密码无效"
                )  # translate Invalid username or password --》用户名或密码无效
                return None, usn, pwd
