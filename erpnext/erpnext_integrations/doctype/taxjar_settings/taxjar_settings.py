# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import json
import os

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.model.document import Document
from frappe.permissions import add_permission, update_permission_property

from erpnext.erpnext_integrations.taxjar_integration import get_client


class TaxJarSettings(Document):

	def on_update(self):
		TAXJAR_CREATE_TRANSACTIONS = frappe.db.get_single_value("TaxJar Settings", "taxjar_create_transactions")
		TAXJAR_CALCULATE_TAX = frappe.db.get_single_value("TaxJar Settings", "taxjar_calculate_tax")
		TAXJAR_SANDBOX_MODE = frappe.db.get_single_value("TaxJar Settings", "is_sandbox")

		if TAXJAR_CREATE_TRANSACTIONS or TAXJAR_CALCULATE_TAX or TAXJAR_SANDBOX_MODE:
			add_product_tax_categories()
			make_custom_fields()
			add_permissions()
			frappe.enqueue('erpnext.regional.united_states.setup.add_product_tax_categories', now=False)

	@frappe.whitelist()
	def update_nexus_list(self):
		client = get_client()
		nexus = client.nexus_regions()

		new_nexus_list = [frappe._dict(address) for address in nexus]

		self.set('nexus', [])
		self.set('nexus', new_nexus_list)
		self.save()

def add_product_tax_categories():
	with open(os.path.join(os.path.dirname(__file__), 'product_tax_category_data.json'), 'r') as f:
		tax_categories = json.loads(f.read())
	create_tax_categories(tax_categories['categories'])

def create_tax_categories(data):
	for d in data:
		tax_category = frappe.new_doc('Product Tax Category')
		tax_category.description = d.get("description")
		tax_category.product_tax_code = d.get("product_tax_code")
		tax_category.category_name = d.get("name")
		try:
			tax_category.db_insert()
		except frappe.DuplicateEntryError:
			pass

def make_custom_fields(update=True):
	custom_fields = {
		'Sales Invoice Item': [
			dict(fieldname='product_tax_category', fieldtype='Link', insert_after='description', options='Product Tax Category',
				label='Product Tax Category', fetch_from='item_code.product_tax_category'),
			dict(fieldname='tax_collectable', fieldtype='Currency', insert_after='net_amount',
				label='Tax Collectable', read_only=1),
			dict(fieldname='taxable_amount', fieldtype='Currency', insert_after='tax_collectable',
				label='Taxable Amount', read_only=1)
		],
		'Item': [
			dict(fieldname='product_tax_category', fieldtype='Link', insert_after='item_group', options='Product Tax Category',
				label='Product Tax Category')
		]
	}
	create_custom_fields(custom_fields, update=update)

def add_permissions():
	doctype = "Product Tax Category"
	for role in ('Accounts Manager', 'Accounts User', 'System Manager','Item Manager', 'Stock Manager'):
		add_permission(doctype, role, 0)
		update_permission_property(doctype, role, 0, 'write', 1)
		update_permission_property(doctype, role, 0, 'create', 1)
