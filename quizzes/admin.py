from django import forms
from django.contrib import admin

from .models import AnswerChoice, Question, Quiz, QuizAttempt, QuizAttemptAnswer


class QuestionInlineForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = '__all__'
        widgets = {
            'text': forms.Textarea(
                attrs={
                    'rows': 3,
                    'class': 'vLargeTextField onedu-admin-question-textarea',
                }
            ),
        }


class QuestionInline(admin.TabularInline):
    model = Question
    form = QuestionInlineForm
    extra = 0
    fields = ('order', 'type', 'text', 'points')
    ordering = ('order',)
    show_change_link = True


class AnswerChoiceInline(admin.TabularInline):
    model = AnswerChoice
    extra = 0
    fields = ('order', 'text', 'is_correct')
    ordering = ('order',)


class QuizAttemptAnswerInline(admin.TabularInline):
    model = QuizAttemptAnswer
    extra = 0
    fields = ('question', 'selected_choice', 'text_answer', 'is_correct', 'earned_points')
    readonly_fields = ('question', 'selected_choice', 'text_answer', 'is_correct', 'earned_points')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'pass_score', 'max_attempts', 'is_public', 'question_count', 'updated_at')
    list_filter = ('is_public', 'course', 'created_at')
    search_fields = ('title', 'description', 'course__title')
    list_select_related = ('course',)
    inlines = [QuestionInline]

    @admin.display(description='문제 수')
    def question_count(self, obj):
        return obj.questions.count()


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'order', 'type', 'points', 'short_text')
    list_filter = ('type', 'quiz__course', 'quiz')
    search_fields = ('text', 'quiz__title', 'quiz__course__title')
    list_select_related = ('quiz', 'quiz__course')
    inlines = [AnswerChoiceInline]
    ordering = ('quiz', 'order')

    @admin.display(description='문제')
    def short_text(self, obj):
        return obj.text[:80]


@admin.register(AnswerChoice)
class AnswerChoiceAdmin(admin.ModelAdmin):
    list_display = ('question', 'order', 'text', 'is_correct')
    list_filter = ('is_correct', 'question__quiz', 'question__quiz__course')
    search_fields = ('text', 'question__text', 'question__quiz__title')
    list_select_related = ('question', 'question__quiz')
    ordering = ('question', 'order')


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'quiz',
        'course_title',
        'attempt_number',
        'score',
        'passed',
        'submitted_at',
    )
    list_filter = ('passed', 'quiz', 'quiz__course', 'submitted_at')
    search_fields = (
        'user__username',
        'user__name',
        'user__email',
        'quiz__title',
        'quiz__course__title',
    )
    list_select_related = ('user', 'quiz', 'quiz__course', 'enrollment')
    readonly_fields = (
        'user',
        'quiz',
        'enrollment',
        'score',
        'max_score',
        'passed',
        'attempt_number',
        'started_at',
        'submitted_at',
    )
    date_hierarchy = 'submitted_at'
    inlines = [QuizAttemptAnswerInline]

    @admin.display(description='강의', ordering='quiz__course__title')
    def course_title(self, obj):
        return obj.quiz.course.title
