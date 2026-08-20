"""Preschool administration.

Every route here was previously anonymous: anyone at all could add, rename or
delete a preschool.
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import api_client
from app.routes.auth import admin_required

preschool_bp = Blueprint('preschool', __name__, url_prefix='/preschools')


@preschool_bp.route('/admin/preschools')
@admin_required
def view_preschools():
    preschools = api_client.get('preschools')['preschools']
    return render_template('PreschoolManagement/view_preschools.html',
                           preschools=preschools)


@preschool_bp.route('/admin/preschool/add', methods=['GET', 'POST'])
@admin_required
def add_preschool():
    if request.method == 'POST':
        try:
            created = api_client.post('preschools',
                                      json={'name': request.form.get('name')})
        except api_client.ApiError as e:
            flash(e.message, 'error')
            return render_template('PreschoolManagement/add_preschool.html')

        flash(f"Added {created['preschool']['name']}", 'success')
        return redirect(url_for('preschool.view_preschools'))

    return render_template('PreschoolManagement/add_preschool.html')


@preschool_bp.route('/admin/preschool/<int:preschool_id>')
@admin_required
def view_preschool(preschool_id):
    try:
        preschool = api_client.get(f'preschools/{preschool_id}')['preschool']
    except api_client.ApiNotFound:
        flash('Preschool not found', 'error')
        return redirect(url_for('preschool.view_preschools'))
    return render_template('PreschoolManagement/view_preschool.html',
                           preschool=preschool)


@preschool_bp.route('/admin/preschool/edit/<int:preschool_id>', methods=['GET', 'POST'])
@admin_required
def edit_preschool(preschool_id):
    try:
        preschool = api_client.get(f'preschools/{preschool_id}')['preschool']
    except api_client.ApiNotFound:
        flash('Preschool not found', 'error')
        return redirect(url_for('preschool.view_preschools'))

    if request.method == 'POST':
        try:
            api_client.patch(f'preschools/{preschool_id}',
                             json={'name': request.form.get('name')})
        except api_client.ApiError as e:
            flash(e.message, 'error')
            return render_template('PreschoolManagement/edit_preschool.html',
                                   preschool=preschool)

        flash('Preschool updated', 'success')
        return redirect(url_for('preschool.view_preschool',
                                preschool_id=preschool_id))

    return render_template('PreschoolManagement/edit_preschool.html',
                           preschool=preschool)


@preschool_bp.route('/admin/preschool/delete/<int:preschool_id>', methods=['POST'])
@admin_required
def delete_preschool(preschool_id):
    # Read the name *before* deleting. The service used to hand back the deleted
    # object so the flash could name it; DELETE returns 204 with no body, so the
    # name has to be captured while the row still exists.
    try:
        preschool = api_client.get(f'preschools/{preschool_id}')['preschool']
        api_client.delete(f'preschools/{preschool_id}')
    except api_client.ApiError as e:
        flash(e.message, 'error')
        return redirect(url_for('preschool.view_preschools'))

    flash(f"Deleted {preschool['name']}", 'success')
    return redirect(url_for('preschool.view_preschools'))