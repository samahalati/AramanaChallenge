from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone

from core.constants import Role, UserStatus


class UserManager(BaseUserManager):
    def create_user(self, email, password, **fields):
        user = self.model(email=email.lower(), **fields)
        user.set_password(password)
        user.save()
        return user


class User(AbstractBaseUser):
    """Identity + role + lifecycle status (the single user table shared by all modules)."""
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=40, choices=Role.choices, db_index=True)
    status = models.CharField(max_length=30, choices=UserStatus.choices, default=UserStatus.ACTIVE, db_index=True)
    failed_logins = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.IntegerField(null=True, blank=True)

    USERNAME_FIELD = "email"
    objects = UserManager()

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    def __str__(self):
        return self.email
