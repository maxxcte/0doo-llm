# models/wizards/fetch_models_wizard.py
from odoo import api, fields, models

class FetchModelsLine(models.TransientModel):
    _name = 'llm.fetch.models.line'
    _description = 'LLM Fetch Models Line'

    wizard_id = fields.Many2one('llm.fetch.models.wizard', required=True)
    name = fields.Char(required=True)
    model_use = fields.Selection([
        ('embedding', 'Embedding'),
        ('completion', 'Completion'),
        ('chat', 'Chat'),
        ('multimodal', 'Multimodal'),
    ], required=True)
    status = fields.Selection([
        ('new', 'New'),
        ('existing', 'Existing'),
        ('modified', 'Modified'),
    ], required=True, default='new')
    selected = fields.Boolean(default=True)
    details = fields.Json()
    existing_model_id = fields.Many2one('llm.model')

class FetchModelsWizard(models.TransientModel):
    _name = 'llm.fetch.models.wizard'
    _description = 'Fetch LLM Models Wizard'

    provider_id = fields.Many2one('llm.provider', required=True)
    line_ids = fields.One2many('llm.fetch.models.line', 'wizard_id', string='Models')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self._context.get('active_id'):
            provider = self.env['llm.provider'].browse(self._context['active_id'])
            res['provider_id'] = provider.id

            # Fetch available models from provider
            try:
                models_data = provider.list_models()
                lines = []

                for model_data in models_data:
                    name = model_data.get('name')
                    if not name:
                        continue

                    # Determine model use based on capabilities
                    capabilities = model_data.get('details', {}).get('capabilities', ['chat'])
                    model_use = 'chat'  # default
                    if 'embedding' in capabilities:
                        model_use = 'embedding'
                    elif 'multimodal' in capabilities:
                        model_use = 'multimodal'

                    # Check if model already exists
                    existing = self.env['llm.model'].search([
                        ('name', '=', name),
                        ('provider_id', '=', provider.id)
                    ])

                    status = 'new'
                    if existing:
                        status = 'modified' if existing.details != model_data.get('details') else 'existing'

                    lines.append((0, 0, {
                        'name': name,
                        'model_use': model_use,
                        'status': status,
                        'details': model_data.get('details'),
                        'existing_model_id': existing.id if existing else False,
                        'selected': status in ['new', 'modified']
                    }))

                res['line_ids'] = lines

            except Exception as e:
                # Handle error gracefully in the UI
                pass

        return res

    def action_confirm(self):
        self.ensure_one()

        for line in self.line_ids.filtered(lambda l: l.selected):
            values = {
                'name': line.name,
                'provider_id': self.provider_id.id,
                'model_use': line.model_use,
                'details': line.details,
                'active': True,
            }

            if line.existing_model_id:
                line.existing_model_id.write(values)
            else:
                self.env['llm.model'].create(values)

        return {'type': 'ir.actions.act_window_close'}