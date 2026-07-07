from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Quiz(models.Model):
    course = models.ForeignKey(
        'courses.Course',
        verbose_name='강의',
        on_delete=models.CASCADE,
        related_name='quizzes',
    )
    title = models.CharField('시험 제목', max_length=200)
    description = models.TextField('시험 설명', blank=True)
    pass_score = models.PositiveSmallIntegerField(
        '합격 점수',
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    is_public = models.BooleanField('공개 여부', default=True)
    max_attempts = models.PositiveSmallIntegerField('재응시 가능 횟수', default=3)
    created_at = models.DateTimeField('생성일', auto_now_add=True)
    updated_at = models.DateTimeField('수정일', auto_now=True)

    class Meta:
        verbose_name = '시험'
        verbose_name_plural = '시험'
        ordering = ['course', 'title']

    def __str__(self):
        return f'{self.course.title} - {self.title}'

    def get_take_url(self):
        return reverse('quizzes:take', kwargs={'pk': self.pk})


class Question(models.Model):
    class Type(models.TextChoices):
        MULTIPLE_CHOICE = 'multiple_choice', '객관식'
        SHORT_ANSWER = 'short_answer', '주관식'

    quiz = models.ForeignKey(
        Quiz,
        verbose_name='시험',
        on_delete=models.CASCADE,
        related_name='questions',
    )
    type = models.CharField('문제 유형', max_length=30, choices=Type.choices)
    text = models.TextField('문제 내용')
    points = models.PositiveSmallIntegerField('배점', default=10)
    order = models.PositiveIntegerField('정렬 순서', default=1)

    class Meta:
        verbose_name = '문제'
        verbose_name_plural = '문제'
        ordering = ['quiz', 'order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['quiz', 'order'], name='unique_question_order_per_quiz'),
        ]

    def __str__(self):
        return f'{self.quiz.title} - {self.order}. {self.text[:40]}'


class AnswerChoice(models.Model):
    question = models.ForeignKey(
        Question,
        verbose_name='문제',
        on_delete=models.CASCADE,
        related_name='choices',
    )
    text = models.CharField('보기 내용', max_length=500)
    is_correct = models.BooleanField('정답 여부', default=False)
    order = models.PositiveIntegerField('정렬 순서', default=1)

    class Meta:
        verbose_name = '객관식 보기'
        verbose_name_plural = '객관식 보기'
        ordering = ['question', 'order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['question', 'order'], name='unique_choice_order_per_question'),
        ]

    def __str__(self):
        return f'{self.question.order}. {self.text[:40]}'


class QuizAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='응시자',
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
    )
    quiz = models.ForeignKey(
        Quiz,
        verbose_name='시험',
        on_delete=models.CASCADE,
        related_name='attempts',
    )
    enrollment = models.ForeignKey(
        'enrollments.Enrollment',
        verbose_name='수강',
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
    )
    score = models.PositiveSmallIntegerField('점수', default=0)
    max_score = models.PositiveSmallIntegerField('만점', default=100)
    passed = models.BooleanField('합격 여부', default=False)
    attempt_number = models.PositiveSmallIntegerField('응시 횟수', default=1)
    started_at = models.DateTimeField('응시 시작 시간', default=timezone.now)
    submitted_at = models.DateTimeField('제출 시간', null=True, blank=True)

    class Meta:
        verbose_name = '시험 응시'
        verbose_name_plural = '시험 응시'
        ordering = ['-submitted_at', '-started_at']
        indexes = [
            models.Index(fields=['user', 'quiz']),
            models.Index(fields=['quiz', 'passed']),
        ]

    def __str__(self):
        return f'{self.user} - {self.quiz.title} ({self.score}점)'


class QuizAttemptAnswer(models.Model):
    attempt = models.ForeignKey(
        QuizAttempt,
        verbose_name='응시',
        on_delete=models.CASCADE,
        related_name='answers',
    )
    question = models.ForeignKey(
        Question,
        verbose_name='문제',
        on_delete=models.PROTECT,
        related_name='attempt_answers',
    )
    selected_choice = models.ForeignKey(
        AnswerChoice,
        verbose_name='선택한 보기',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='attempt_answers',
    )
    text_answer = models.TextField('주관식 답안', blank=True)
    is_correct = models.BooleanField('정답 여부', default=False)
    earned_points = models.PositiveSmallIntegerField('획득 점수', default=0)

    class Meta:
        verbose_name = '응시 답안'
        verbose_name_plural = '응시 답안'
        ordering = ['question__order']
        constraints = [
            models.UniqueConstraint(fields=['attempt', 'question'], name='unique_answer_per_attempt_question'),
        ]

    def __str__(self):
        return f'{self.attempt} - {self.question.order}'
