"""Command line tasks: `flask <command>`."""
import click

from config import app, db
from models import (
    Activity,
    Child,
    Feedback,
    LearningPlan,
    Parent,
    Preschool,
    Progress,
    Result,
    Reward,
    Role,
    StemCode,
    Story,
    Teacher,
    User,
)
from seeds import seed_all


def _echo_credentials(label, username, password):
    if password:
        click.echo(f"  {label:<9} {username:<10} password: {password}")
    else:
        click.echo(f"  {label:<9} {username:<10} (already existed, password unchanged)")


@app.cli.command("init-db")
def init_db():
    """Create any missing tables."""
    db.create_all()
    click.echo("Database tables created.")


@app.cli.command("reset-db")
@click.option('--yes', is_flag=True, help="Skip the confirmation prompt.")
def reset_db(yes):
    """Drop and recreate every table. Destroys all data."""
    if not yes:
        click.confirm("This deletes every row in the database. Continue?", abort=True)
    db.drop_all()
    db.create_all()
    click.echo("Database has been reset.")


@app.cli.command("create-admin")
def create_admin():
    """Create the administrator account."""
    from seeds import seed_admin
    admin, password = seed_admin()
    if password is None:
        click.echo(f"Admin user '{admin.username}' already exists.")
    else:
        click.echo(f"Admin user '{admin.username}' created.")
        click.echo(f"  password: {password}")
        click.echo("  Store this now -- it is not shown again.")


@app.cli.command("seed")
@click.option('--demo/--no-demo', default=True,
              help="Also create the demo teacher, parent and children.")
@click.option('--password', default=None,
              help="Password for the demo accounts. Generated if omitted.")
def seed(demo, password):
    """Populate the database with starter users and learning content.

    Safe to run more than once: anything already present is left alone.
    """
    db.create_all()
    summary = seed_all(with_demo=demo, password=password)

    click.echo(f"Activities added: {summary['activities_added']}")
    click.echo(f"Stories added:    {summary['stories_added']}")
    click.echo("")
    click.echo("Accounts:")
    _echo_credentials('admin', summary['admin'].username, summary['admin_password'])

    if summary['demo']:
        info = summary['demo']
        shared = info['password'] if info['created'] else None
        for role, username in (('teacher', info['teacher'].username),
                               ('parent', info['parent'].username)):
            _echo_credentials(role, username,
                              shared if any(u == username for _, u in info['created']) else None)
        for child in info['children']:
            _echo_credentials('child', child.username,
                              shared if any(u == child.username for _, u in info['created']) else None)
        if info['created']:
            click.echo("")
            click.echo("  Store these now -- they are not shown again.")

    click.echo("")
    click.echo("Run `flask check` to verify everything is wired up.")


@app.cli.command("check")
def check():
    """Verify the data is complete and correctly connected.

    Walks the relationship graph the app depends on and reports anything that
    would produce an empty page or a crash at runtime.
    """
    problems = []
    notes = []

    def problem(message):
        problems.append(message)

    # --- users ------------------------------------------------------------
    counts = {
        'admins': User.query.filter_by(role=Role.ADMIN).count(),
        'teachers': Teacher.query.count(),
        'parents': Parent.query.count(),
        'children': Child.query.count(),
        'preschools': Preschool.query.count(),
    }
    click.echo("Users")
    for label, count in counts.items():
        click.echo(f"  {label:<11} {count}")
    if counts['admins'] == 0:
        problem("No admin account exists; run `flask create-admin`.")

    # --- content ----------------------------------------------------------
    activities = Activity.query.all()
    stories = Story.query.all()
    click.echo("")
    click.echo("Content")
    click.echo(f"  activities  {len(activities)}")
    click.echo(f"  stories     {len(stories)}")

    by_strand = {code.name: 0 for code in StemCode}
    for activity in activities:
        if activity.stem_code is None:
            problem(f"Activity {activity.id} '{activity.title}' has no STEM subject.")
            continue
        by_strand[activity.stem_code.name] += 1

        if not activity.questions:
            problem(f"Activity '{activity.title}' has no questions.")
        for question in activity.questions:
            correct = [a for a in question.answers if a.is_correct]
            if len(question.answers) < 2:
                problem(f"'{activity.title}' / '{question.content}' has fewer than two answers.")
            if len(correct) != 1:
                problem(f"'{activity.title}' / '{question.content}' has "
                        f"{len(correct)} correct answers (expected exactly 1).")

    for strand, count in by_strand.items():
        marker = ' ' if count else '!'
        click.echo(f"  {marker} {strand.lower():<12} {count} activities")
        if not count:
            notes.append(f"No activities for {strand}; that strand will look empty.")

    for story in stories:
        if not story.pages:
            problem(f"Story '{story.title}' has no pages.")
        numbers = [page.page_number for page in story.pages]
        if len(set(numbers)) != len(numbers):
            problem(f"Story '{story.title}' has duplicate page numbers.")

    # --- the relationship graph ------------------------------------------
    click.echo("")
    click.echo("Connections")
    for child in Child.query.all():
        who = f"child '{child.username}'"
        if child.parent is None:
            problem(f"{who} has no parent.")
        elif child not in child.parent.children:
            problem(f"{who} is not listed under parent '{child.parent.username}'.")

        if child.teacher is None:
            notes.append(f"{who} has no teacher assigned.")
        elif child not in child.teacher.students:
            problem(f"{who} is not listed under teacher '{child.teacher.username}'.")

        if child.preschool is None:
            notes.append(f"{who} is not linked to a preschool.")

        if child.learning_plan is None:
            problem(f"{who} has no learning plan; activities and stories will be hidden.")
        else:
            for strand in StemCode:
                if child.learning_plan.get_level(strand) is None:
                    problem(f"{who} has no {strand.name.lower()} level in their learning plan.")

        if child.recommended_level is None:
            problem(f"{who} has no recommended level.")

    plans = LearningPlan.query.count()
    click.echo(f"  learning plans   {plans} for {counts['children']} children")
    click.echo(f"  progress rows    {Progress.query.count()}")
    click.echo(f"  results          {Result.query.count()}")
    click.echo(f"  rewards          {Reward.query.count()}")
    click.echo(f"  feedback         {Feedback.query.count()}")

    # --- referential sanity ----------------------------------------------
    for progress in Progress.query.all():
        if progress.learning_content is None:
            problem(f"Progress {progress.id} points at content that no longer exists.")
        if progress.child is None:
            problem(f"Progress {progress.id} points at a child that no longer exists.")
    for result in Result.query.all():
        if result.activity is None or result.child is None:
            problem(f"Result {result.id} has a dangling reference.")
    for reward in Reward.query.all():
        if (reward.activity_id is None) == (reward.story_id is None):
            problem(f"Reward {reward.id} must belong to exactly one activity or story.")
    for message in Feedback.query.all():
        if message.sender is None or message.recipient is None:
            problem(f"Feedback {message.id} has a dangling sender or recipient.")

    # --- what each role would actually see --------------------------------
    click.echo("")
    click.echo("Visibility")
    from services.learning_plan_service import LearningPlanService
    plan_service = LearningPlanService()
    for child in Child.query.all():
        recommended = plan_service.recommend_activities(child.id)
        activity_count = sum(1 for item in recommended if isinstance(item, Activity))
        story_count = sum(1 for item in recommended if isinstance(item, Story))
        click.echo(f"  {child.username:<8} sees {activity_count} activities "
                   f"and {story_count} stories")
        if not recommended:
            problem(f"child '{child.username}' can see no content at all.")

    # --- report -----------------------------------------------------------
    click.echo("")
    if notes:
        click.echo("Notes:")
        for note in notes:
            click.echo(f"  - {note}")
    if problems:
        click.echo(click.style(f"{len(problems)} problem(s):", fg='red'))
        for message in problems:
            click.echo(click.style(f"  - {message}", fg='red'))
        raise SystemExit(1)

    click.echo(click.style("All checks passed.", fg='green'))


@app.cli.command("import-content")
@click.argument('path', type=click.Path(exists=True, dir_okay=False))
def import_content(path):
    """Load activities and stories from a JSON file.

    The file takes the same shape as seeds/content.py:
    {"activities": [...], "stories": [...]}
    """
    import json

    from seeds import content as content_module

    with open(path, encoding='utf-8') as handle:
        payload = json.load(handle)

    original = (content_module.ACTIVITIES, content_module.STORIES)
    content_module.ACTIVITIES = payload.get('activities', [])
    content_module.STORIES = payload.get('stories', [])
    try:
        # seed_content reads the module attributes, so patching them lets the
        # same insert-and-skip logic serve file imports too.
        import seeds.seeder as seeder_module
        from seeds.seeder import seed_content
        seeder_module.ACTIVITIES = content_module.ACTIVITIES
        seeder_module.STORIES = content_module.STORIES
        activities, stories = seed_content()
    finally:
        content_module.ACTIVITIES, content_module.STORIES = original
        import seeds.seeder as seeder_module
        seeder_module.ACTIVITIES, seeder_module.STORIES = original

    click.echo(f"Imported {activities} activities and {stories} stories from {path}.")
