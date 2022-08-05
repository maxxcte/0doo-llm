from odoo import api, fields, models

class FetchModelsLine(models.TransientModel):
    _name = 'llm.fetch.models.line'
    _description = 'LLM Fetch Models Line'

    wizard_id = fields.Many2one('llm.fetch.models.wizard', required=True, ondelete='cascade')
    name = fields.Char(string='Model Name', required=True)
    model_use = fields.Selection([
        ('embedding', 'Embedding'),
        ('completion', 'Completion'),
        ('chat', 'Chat'),
        ('multimodal', 'Multimodal'),
    ], required=True, default='chat')
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

        if not self._context.get('active_id'):
            return res

        provider = self.env['llm.provider'].browse(self._context['active_id'])
        res['provider_id'] = provider.id

        # Fetch models from provider
        models_data = list(provider.list_models())
        lines = []

        for model_data in models_data:
            details = model_data.get('details', {})

            # Use model id as name if name not provided
            name = model_data.get('name') or details.get('id')
            if not name:
                continue

            # Determine model use based on capabilities and name
            capabilities = details.get('capabilities', ['chat'])
            model_use = 'chat'  # default

            if any(cap in capabilities for cap in ['embedding', 'text-embedding']) or 'embedding' in name.lower():
                model_use = 'embedding'
            elif any(cap in capabilities for cap in ['multimodal', 'vision']):
                model_use = 'multimodal'

            # Check for existing model
            existing = self.env['llm.model'].search([
                ('name', '=', name),
                ('provider_id', '=', provider.id)
            ], limit=1)

            status = 'new'
            if existing:
                status = 'modified' if existing.details != details else 'existing'

            line_vals = {
                'name': name,
                'model_use': model_use,
                'status': status,
                'details': details,
                'existing_model_id': existing.id if existing else False,
                'selected': status in ['new', 'modified']
            }

            lines.append((0, 0, line_vals))

        if lines:
            res['line_ids'] = lines

        return res

    def action_confirm(self):
        self.ensure_one()
        Model = self.env['llm.model']

        for line in self.line_ids.filtered(lambda l: l.selected and l.name):
            values = {
                'name': line.name.strip(),
                'provider_id': self.provider_id.id,
                'model_use': line.model_use,
                'details': line.details,
                'active': True,
            }

            if line.existing_model_id:
                line.existing_model_id.write(values)
            else:
                Model.create(values)

        return {'type': 'ir.actions.act_window_close'}