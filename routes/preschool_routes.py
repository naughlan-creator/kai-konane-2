from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.preschool import Preschool
from services.preschool_service import PreschoolService
from config import db

preschool_service = PreschoolService(db)

preschool_bp = Blueprint('preschool', __name__, url_prefix='/preschools')

@preschool_bp.route('/admin/preschools')
def view_preschools():
    preschools = preschool_service.get_preschools()
    return render_template('PreschoolManagement/view_preschools.html', preschools=preschools)

@preschool_bp.route('/admin/preschool/add', methods=['GET', 'POST'])
def add_preschool():
    if request.method == 'POST':
        name = request.form['name']
        new_preschool = Preschool(name=name)
        result = preschool_service.add_preschool(new_preschool)
        flash(result)
        return redirect(url_for('preschool.view_preschools'))
    return render_template('PreschoolManagement/add_preschool.html')

@preschool_bp.route('/admin/preschool/<int:preschool_id>')
def view_preschool(preschool_id):
    preschool = preschool_service.get_preschool(preschool_id)
    if preschool:
        return render_template('PreschoolManagement/view_preschool.html', preschool=preschool)
    flash('Preschool not found')
    return redirect(url_for('preschool.view_preschools'))

@preschool_bp.route('/admin/preschool/edit/<int:preschool_id>', methods=['GET', 'POST'])
def edit_preschool(preschool_id):
    preschool = preschool_service.get_preschool(preschool_id)
    if not preschool:
        flash('Preschool not found')
        return redirect(url_for('preschool.view_preschools'))

    if request.method == 'POST':
        preschool.name = request.form['name']
        result = preschool_service.update_preschool(preschool)
        flash(result)
        return redirect(url_for('preschool.view_preschool', preschool_id=preschool_id))

    return render_template('PreschoolManagement/edit_preschool.html', preschool=preschool)

@preschool_bp.route('/admin/preschool/delete/<int:preschool_id>', methods=['POST'])
def delete_preschool(preschool_id):
    result = preschool_service.delete_preschool(preschool_id)
    flash(result)
    return redirect(url_for('preschool.view_preschools'))
