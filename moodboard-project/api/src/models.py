from sqlalchemy import Column, Integer, String, Boolean, Text, TIMESTAMP, ForeignKey, JSON, BigInteger, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True)
    username = Column(String(50), unique=True, nullable=False)
    is_registered = Column(Boolean, default=False)
    website_login = Column(String(50), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)
    plain_password = Column(String(100), nullable=True)

    owned_boards = relationship("Board", back_populates="owner")
    board_memberships = relationship("BoardMember", back_populates="user")
    created_content = relationship("ContentItem", back_populates="creator")



class Board(Base):
    __tablename__ = "boards"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    view_token = Column(String(50), unique=True, nullable=False)
    board_code = Column(String(20), unique=True, nullable=False)
    is_public = Column(Boolean, default=False)
    background_color = Column(String(20), default="#FFFBF0")
    border_color = Column(String(20), default="#5D4037")
    board_width = Column(Integer, default=1200)
    board_height = Column(Integer, default=900)
    created_at = Column(TIMESTAMP, server_default=func.now())
    owner_id = Column(BigInteger, ForeignKey("users.id"))

    owner = relationship("User", back_populates="owned_boards")
    members = relationship("BoardMember", back_populates="board")
    content_items = relationship("ContentItem", back_populates="board", cascade="all, delete-orphan")



class BoardMember(Base):
    __tablename__ = "board_members"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'collaborator')", name='check_role_values'),
    )

    board_id = Column(BigInteger, ForeignKey("boards.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role = Column(String(15), nullable=False)

    board = relationship("Board", back_populates="members")
    user = relationship("User", back_populates="board_memberships")



class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        CheckConstraint("type IN ('text', 'image')", name='check_type_values'),
    )

    id = Column(BigInteger, primary_key=True, index=True)
    board_id = Column(BigInteger, ForeignKey("boards.id", ondelete="CASCADE"))
    type = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    x_position = Column(Integer, default=0)
    y_position = Column(Integer, default=0)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    z_index = Column(Integer, default=1)
    media_metadata = Column(JSON, nullable=True)
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    board = relationship("Board", back_populates="content_items")
    creator = relationship("User", back_populates="created_content")