# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MailMessage(models.Model):
    _inherit = "mail.message"

    user_vote = fields.Integer(
        string="User Vote",
        default=0,
        help="Vote status given by the user. 0: No vote, 1: Upvoted, -1: Downvoted."
    )


    def message_format(self, format_reply=True):
        """Override message_format to mark tool messages as notes for proper UI rendering"""
        vals_list = super().message_format(format_reply=format_reply)

        # Update is_note for tool messages
        for vals in vals_list:
            message_sudo = self.browse(vals["id"]).sudo().with_prefetch(self.ids)
            vals["user_vote"] = message_sudo.user_vote

        return vals_list
