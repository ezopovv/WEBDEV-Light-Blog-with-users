from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentsForm
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap5(app)

#Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app) # can configure it for login

#Gravatar
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///posts.db")
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES
class User(db.Model, UserMixin):
    #__tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100),unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(250), nullable=False)
    # Связь с таблицами BlogPost, Comments
    posts: Mapped[list["BlogPost"]] = relationship(back_populates="author", cascade="all, delete")
    comments: Mapped[list["Comment"]] = relationship(back_populates="comment_author", cascade="all, delete")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    # Связь с таблицей User
    author: Mapped["User"] = relationship(back_populates="posts")
    # Связь с таблицей Comment
    comments: Mapped[list["Comment"]] = relationship(back_populates="parent_post", cascade="all, delete")

class Comment(db.Model):
    __tablename__= "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    # Связь с таблицей User
    comment_author: Mapped["User"] = relationship(back_populates="comments")
    # Связь с таблицей BlogPost
    post_id: Mapped[int] = mapped_column(ForeignKey("blog_posts.id"), nullable=False)
    parent_post: Mapped["BlogPost"] = relationship(back_populates="comments")



with app.app_context():
    db.create_all()

#provide a user_loader callback.
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)

#difining admin decorator
def admin_only(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated and current_user.id != 1:
            abort(403)
        return func(*args, **kwargs)
    return wrapper



@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if request.method == "POST":

        if db.session.execute(db.select(User.email).where(User.email == request.form.get("email"))).scalar():
            flash("This email already exists. Please login.")
            return redirect(url_for("login"))

        user = User(
            name=request.form.get("name"),
            email=request.form.get("email"),
            password=generate_password_hash(password=request.form.get("password"), method="pbkdf2", salt_length=8)
        )
        db.session.add(user)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    password = request.form.get("password")
    if request.method == "POST" and form.validate_on_submit():
        user = db.session.execute(db.Select(User).where(User.email == request.form.get("email"))).scalar()

        if not user:
            flash('Email does not exist. Please try again.')
            return render_template("login.html", form=form)

        if user and not check_password_hash(user.password, password):
            flash('Incorrect password. Please try again.')
            return render_template("login.html", form=form)

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("get_all_posts"))
    return render_template("login.html", form = form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    # for post in posts:
    #     print(post.author.name)
    return render_template("index.html", all_posts=posts)


# Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentsForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    comments = db.session.execute(db.select(Comment).where(Comment.post_id == post_id)).scalars().all()
    if form.validate_on_submit() and request.method == "POST":
        if current_user.is_authenticated:
            comment = Comment(text = form.comment.data,
                              comment_author=current_user,
                              post_id=post_id)
            print(vars(comment))
            db.session.add(comment)
            db.session.commit()
            return render_template("post.html", post=requested_post, form=form, comments=comments)
        else:
            flash("You need to login")
            return redirect(url_for("login"))
    return render_template("post.html", post=requested_post, form=form, comments=comments)



@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)



@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=False)
