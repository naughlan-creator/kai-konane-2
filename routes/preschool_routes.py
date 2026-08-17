from flask import Blueprint, flash, redirect, render_template, request, url_for

from config import db
from routes.auth import admin_required
from services.errors import ServiceError
from services.preschool_service import PreschoolService

preschool_service = PreschoolService(db)

preschool_bp = Blueprint('preschool', __name__, url_prefix='/preschools')

# Every route here was previously anonymous: anyone at all could add, rename or
# delete a preschool.


@preschool_bp.route('/admin/preschools')
@admin_required
def view_preschools():
    preschools = preschool_service.get_preschools()
    return render_template('PreschoolManagement/view_preschools.html', preschools=preschools)


@preschool_bp.route('/admin/preschool/add', methods=['GET', 'POST'])
@admin_required
def add_preschool():
    if request.method == 'POST':
        try:
            preschool = preschool_service.add_preschool(request.form.get('name'))
        except ServiceError as e:
            flash(str(e), 'error')
            return render_template('PreschoolManagement/add_preschool.html')

        flash(f"Added {preschool.name}", 'success')
        return redirect(url_for('preschool.view_preschools'))

    return render_template('PreschoolManagement/add_preschool.html')


@preschool_bp.route('/admin/preschool/<int:preschool_id>')
@admin_required
def view_preschool(preschool_id):
    preschool = preschool_service.get_preschool(preschool_id)
    if preschool is None:
        flash('Preschool not found', 'error')
        return redirect(url_for('preschool.view_preschools'))
    return render_template('PreschoolManagement/view_preschool.html', preschool=preschool)


@preschool_bp.route('/admin/preschool/edit/<int:preschool_id>', methods=['GET', 'POST'])
@admin_required
def edit_preschool(preschool_id):
    preschool = preschool_service.get_preschool(preschool_id)
    if preschool is None:
        flash('Preschool not found', 'error')
        return redirect(url_for('preschool.view_preschools'))

    if request.method == 'POST':
        try:
            preschool_service.update_preschool(preschool_id, request.form.get('name'))
        except ServiceError as e:
            flash(str(e), 'error')
            return render_template('PreschoolManagement/edit_preschool.html',
                                   preschool=preschool)

        flash('Preschool updated', 'success')
        return redirect(url_for('preschool.view_preschool', preschool_id=preschool_id))

    return render_template('PreschoolManagement/edit_preschool.html', preschool=preschool)


@preschool_bp.route('/admin/preschool/delete/<int:preschool_id>', methods=['POST'])
@admin_required
def delete_preschool(preschool_id):
    try:
        preschool = preschool_service.delete_preschool(preschool_id)
    except ServiceError as e:
        flash(str(e), 'error')
        return redirect(url_for('preschool.view_preschools'))

    flash(f"Deleted {preschool.name}", 'success')
    return redirect(url_for('preschool.view_preschools'))
