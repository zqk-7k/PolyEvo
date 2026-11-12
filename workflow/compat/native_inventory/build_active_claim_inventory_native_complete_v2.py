"""Self-contained native-complete inventory, preserving the frozen legacy C prefix.

Only exact publication objects are containers; no scientific scope/support verdict.
The original inventory source is embedded and SHA256 bound, never mutable-imported.
"""
import argparse
import ast
import base64
import hashlib
import json
import sys
from pathlib import Path

COLLECTION = 'additional_native_owner_contexts'
AUDIT = 'native_owner_completion_audit'
LEGACY_SOURCE_SHA256 = 'b64795abaf52d34da9dbe7f9ae6a29f492830ff6ae9e11cb071ec7fe5b51304b'
LEGACY_SOURCE_BASE64 = 'IiIiRW51bWVyYXRlIGNvbXBsZXRlIG91dHB1dCBjb250YWluZXJzIGZvciBsYXRlciBzb3VyY2Uvc2NvcGUvZGVkdXAgcmV2aWV3LgoKVGhlc2UgYXJlIHJldmlldyBjb250YWluZXJzLCBub3QgbWV0cmljIHVuaXRzLiBObyBzZW1hbnRpYyBjYXRlZ29yeSwgc291cmNlCnN1cHBvcnQsIG9yIG91dHB1dCBleGNsdXNpb24gaXMgY2VydGlmaWVkIG1lcmVseSBieSBiZWluZyBpbiB0aGlzIGludmVudG9yeS4KIiIiCmZyb20gcGF0aGxpYiBpbXBvcnQgUGF0aAppbXBvcnQgYXJncGFyc2UKaW1wb3J0IGhhc2hsaWIKaW1wb3J0IGpzb24KZnJvbSBldmFsdWF0aW9uX2ludGVncml0eSBpbXBvcnQgcmVqZWN0X29wdGltaXplZAoKCmRlZiBjYW5vbmljYWwodmFsdWUpOgogICAgcmV0dXJuIGhhc2hsaWIuc2hhMjU2KGpzb24uZHVtcHModmFsdWUsZW5zdXJlX2FzY2lpPUZhbHNlLHNvcnRfa2V5cz1UcnVlLAogICAgICAgIHNlcGFyYXRvcnM9KCcsJywnOicpKS5lbmNvZGUoKSkuaGV4ZGlnZXN0KCkKCgpkZWYgaW52ZW50b3J5KHByZWRpY3Rpb24pOgogICAgcm93cz1bXQogICAgZGVmIGFkZChwYXRoLHZhbHVlLHJvbGUsaW5pdGlhbF9raW5kPU5vbmUscHVibGljYXRpb249J2FjdGl2ZScpOgogICAgICAgIHJvd3MuYXBwZW5kKGRpY3QoaWQ9J0MnK3N0cihsZW4ocm93cykrMSkuemZpbGwoNikscHJlZGljdGlvbl9wYXRoPXBhdGgsCiAgICAgICAgICAgIGNvbXBsZXRlX2NvbnRhaW5lcl9zaGEyNTY9Y2Fub25pY2FsKHZhbHVlKSxyb2xlPXJvbGUsaW5pdGlhbF9raW5kX2hpbnQ9aW5pdGlhbF9raW5kLAogICAgICAgICAgICBwdWJsaWNhdGlvbl9ib3VuZGFyeT1wdWJsaWNhdGlvbixjb21wbGV0ZV9jb250YWluZXI9dmFsdWUsCiAgICAgICAgICAgIHNjb3BlX3NlbWFudGljc19hbmRfZnVsbF9jb25qdW5jdGlvbl9ub3RfeWV0X3Jldmlld2VkPVRydWUpKQogICAgc2VtYW50aWM9cHJlZGljdGlvbi5nZXQoJ2FjdGl2ZV9wcmltYXJ5X3Byb2Nlc3NfZ3JhcGgnKT09J3NvdXJjZV9zZW1hbnRpY19ncmFwaCcKICAgIGZpZWxkPSdzb3VyY2Vfc2VtYW50aWNfZ3JhcGgnIGlmIHNlbWFudGljIGVsc2UgJ3Byb2Nlc3NfZ3JhcGgnCiAgICBncmFwaD1wcmVkaWN0aW9uW2ZpZWxkXQogICAgZm9yIGtleSxraW5kIGluIFsoJ21hdGVyaWFsX2lkZW50aXRpZXMnLCdiaW5kaW5nJyksKCdzdGF0ZXMnLCdzdGF0ZScpLCgnb3BlcmF0aW9ucycsJ29wZXJhdGlvbicpLAogICAgICAgICAgICAoJ3BhcmFtZXRlcnMnLCdwYXJhbWV0ZXInKSwoJ29yZGVycycsJ29yZGVyJyksKCdiaW5kaW5ncycsJ2JpbmRpbmcnKV06CiAgICAgICAgZm9yIGkscm93IGluIGVudW1lcmF0ZShncmFwaC5nZXQoa2V5LFtdKSk6CiAgICAgICAgICAgIGFkZCgnLycrZmllbGQrJy8nK2tleSsnLycrc3RyKGkpLHJvdywncHJpbWFyeV9ncmFwaF8nK2tleSxraW5kKQogICAgZm9yIGtleSBpbiBbJ25vbnBoeXNpY2FsX2Fubm90YXRpb25zJywndW5yZXNvbHZlZF9zb3VyY2VfaXRlbXMnXToKICAgICAgICBmb3IgaSxyb3cgaW4gZW51bWVyYXRlKGdyYXBoLmdldChrZXksW10pKToKICAgICAgICAgICAgYWRkKCcvJytmaWVsZCsnLycra2V5KycvJytzdHIoaSkscm93LCdzb3VyY2Vfc2NvcGVfb3JfdW5jZXJ0YWludHlfYW5ub3RhdGlvbicsCiAgICAgICAgICAgICAgICBwdWJsaWNhdGlvbj0nZGlhZ25vc3RpY19vcl9ub25waHlzaWNhbF9jbGFpbV9zY29wZV9tdXN0X2JlX3Jldmlld2VkJykKICAgIGdyYXBoX21ldGFkYXRhPXsnc2NoZW1hX3ZlcnNpb24nLCdyZWZlcmVuY2Vfbm8nLCdzb3VyY2VfZG9jdW1lbnRfc2hhMjU2Jywnc291cmNlX2NvdmVyYWdlJ30KICAgIGdyYXBoX2VudW1lcmF0ZWQ9eydtYXRlcmlhbF9pZGVudGl0aWVzJywnc3RhdGVzJywnb3BlcmF0aW9ucycsJ3BhcmFtZXRlcnMnLCdvcmRlcnMnLCdiaW5kaW5ncycsCiAgICAgICAgJ25vbnBoeXNpY2FsX2Fubm90YXRpb25zJywndW5yZXNvbHZlZF9zb3VyY2VfaXRlbXMnLCduYXRpdmVfZGlzcG9zaXRpb25zJ30KICAgIGlmIG5vdCBzZW1hbnRpYzogZ3JhcGhfZW51bWVyYXRlZC5yZW1vdmUoJ25hdGl2ZV9kaXNwb3NpdGlvbnMnKQogICAgZm9yIGtleSBpbiBzb3J0ZWQoc2V0KGdyYXBoKS1ncmFwaF9tZXRhZGF0YS1ncmFwaF9lbnVtZXJhdGVkKToKICAgICAgICB0b2tlbj1rZXkucmVwbGFjZSgnficsJ34wJykucmVwbGFjZSgnLycsJ34xJykKICAgICAgICBhZGQoJy8nK2ZpZWxkKycvJyt0b2tlbixncmFwaFtrZXldLCd1bmNsYXNzaWZpZWRfZ3JhcGhfZXh0ZW5zaW9uJywKICAgICAgICAgICAgcHVibGljYXRpb249J3VuY2xhc3NpZmllZF9leHRlbnNpb25fcmVxdWlyZXNfc2NvcGVfcmV2aWV3JykKICAgIGZvciBpLHJvdyBpbiBlbnVtZXJhdGUocHJlZGljdGlvbi5nZXQoJ2VmZmVjdGl2ZV9wcm9jZXNzX2NvbnRleHRzJyxbXSkpOgogICAgICAgIGFkZCgnL2VmZmVjdGl2ZV9wcm9jZXNzX2NvbnRleHRzLycrc3RyKGkpLHJvdywnZnVsbF9wcm9wZXJ0eV9vd25lcl9wcm9jZXNzX2NvbnRleHQnKQogICAgZm9yIGkscm93IGluIGVudW1lcmF0ZShwcmVkaWN0aW9uLmdldCgncmVjb3ZlcmVkX29wZXJhdGlvbl9oaXN0b3J5JyxbXSkpOgogICAgICAgIGFkZCgnL3JlY292ZXJlZF9vcGVyYXRpb25faGlzdG9yeS8nK3N0cihpKSxyb3csJ2FjdGl2ZV9kZXRlcm1pbmlzdGljX2Rlc2NyaXB0aW9uX3JlY292ZXJ5JykKICAgIGZvciBpLHJvdyBpbiBlbnVtZXJhdGUocHJlZGljdGlvbi5nZXQoJ3VuY29uZmlybWVkX25hdGl2ZV9jbGFpbXNfc3RpbGxfYWN0aXZlX2Zvcl9vdXRwdXRfc3VwcG9ydCcsW10pKToKICAgICAgICBhZGQoJy91bmNvbmZpcm1lZF9uYXRpdmVfY2xhaW1zX3N0aWxsX2FjdGl2ZV9mb3Jfb3V0cHV0X3N1cHBvcnQvJytzdHIoaSkscm93LAogICAgICAgICAgICAncmV0YWluZWRfdW5jb25maXJtZWRfbmF0aXZlX2NsYWltJykKICAgIGZvciBpLHJvdyBpbiBlbnVtZXJhdGUocHJlZGljdGlvbi5nZXQoJ3BlbmRpbmdfaGlzdG9yeV9yZWNvdmVyeScsW10pKToKICAgICAgICBhZGQoJy9wZW5kaW5nX2hpc3RvcnlfcmVjb3ZlcnkvJytzdHIoaSkscm93LCd1bmFjY2VwdGVkX2RpYWdub3N0aWNfcHJvcG9zYWwnLAogICAgICAgICAgICBwdWJsaWNhdGlvbj0nZGlhZ25vc3RpY19wcm9wb3NhbF9ub3RfYXV0b21hdGljYWxseV9leGNsdWRlZF9mcm9tX3JldmlldycpCiAgICBpZiBzZW1hbnRpYzoKICAgICAgICBhZGQoJy9zb3VyY2Vfc2VtYW50aWNfZ3JhcGgvbmF0aXZlX2Rpc3Bvc2l0aW9ucycsZ3JhcGguZ2V0KCduYXRpdmVfZGlzcG9zaXRpb25zJyxbXSksCiAgICAgICAgICAgICduYXRpdmVfcmV2aXNpb25fZGlzcG9zaXRpb25zJyxwdWJsaWNhdGlvbj0ncmV2aXNpb25fbGluZWFnZV9ib3VuZGFyeV9yZXF1aXJlc19yZXZpZXcnKQogICAgICAgIGFkZCgnL25hdGl2ZV9wcm9jZXNzX2NvbnRleHQnLHByZWRpY3Rpb24uZ2V0KCduYXRpdmVfcHJvY2Vzc19jb250ZXh0Jyx7fSksCiAgICAgICAgICAgICdjb21wbGV0ZV9uYXRpdmVfcmV2aXNpb25fY29udGV4dCcscHVibGljYXRpb249J3JldmlzaW9uX2xpbmVhZ2VfYm91bmRhcnlfcmVxdWlyZXNfcmV2aWV3JykKICAgICAgICBhZGQoJy9wcm9jZXNzX2dyYXBoJyxwcmVkaWN0aW9uLmdldCgncHJvY2Vzc19ncmFwaCcse30pLCdub25wcmltYXJ5X25hdGl2ZV9ncmFwaF9ib3VuZGFyeScsCiAgICAgICAgICAgIHB1YmxpY2F0aW9uPSdub25wcmltYXJ5X2dyYXBoX2lzX25vdF9hdXRvbWF0aWNhbGx5X2V4Y2x1ZGVkX2Zyb21fcmV2aWV3JykKICAgIGVsc2U6CiAgICAgICAgYWRkKCcvbmF0aXZlX3Byb2Nlc3NfY29udGV4dCcscHJlZGljdGlvbi5nZXQoJ25hdGl2ZV9wcm9jZXNzX2NvbnRleHQnLHt9KSwnYWN0aXZlX25hdGl2ZV9wcm9jZXNzX2NvbnRleHQnKQogICAgICAgIGlmICdzb3VyY2Vfc2VtYW50aWNfZ3JhcGgnIGluIHByZWRpY3Rpb246CiAgICAgICAgICAgIGFkZCgnL3NvdXJjZV9zZW1hbnRpY19ncmFwaCcscHJlZGljdGlvblsnc291cmNlX3NlbWFudGljX2dyYXBoJ10sJ25vbnByaW1hcnlfc291cmNlX2dyYXBoX2JvdW5kYXJ5JywKICAgICAgICAgICAgICAgIHB1YmxpY2F0aW9uPSdub25wcmltYXJ5X2dyYXBoX2lzX25vdF9hdXRvbWF0aWNhbGx5X2V4Y2x1ZGVkX2Zyb21fcmV2aWV3JykKICAgIHJvb3RfbWV0YWRhdGE9eyd2ZXJzaW9uJywnZXhlY3V0aW9uX21vZGUnLCdwcm9wZXJ0eV9zb3VyY2UnLCdvcmlnaW5hbF9zdGFnZTBfc291cmNlJywKICAgICAgICAncHJvcGVydHlfdmFsdWVzX3VuaXRzX3NhbXBsZV9pZHNfYW5kX2JpbmRpbmdzX3VuY2hhbmdlZCcsCiAgICAgICAgJ2FsbF9maXZlX3JlZmVyZW5jZV9jb3ZlcmFnZV9hbmRfb3V0cHV0X3N1cHBvcnRfbm90X3lldF9zY29yZWQnLCdub19yZWZlcmVuY2Vfb3Jfc2NvcmVfaW5wdXRzJywKICAgICAgICAnbm9faGlzdG9yaWNhbF9wZXJfcGFwZXJfYWNjZXB0YW5jZV9pbnB1dHMnLCdjb21wbGV0ZV8xNThfcGFwZXJfc3BlY2lmaWNfc291cmNlX2dyYXBoc19ub3RfaW5oZXJpdGVkJywKICAgICAgICAnc291cmNlX2xvY2F0aW9uX2FsaWdubWVudF9kb2VzX25vdF9jZXJ0aWZ5X3NlbWFudGljX3N1cHBvcnQnLCdleHRlcm5hbF9hcGlfY2FsbHMnLCdyZWZlcmVuY2Vfbm8nLAogICAgICAgICdzZW1hbnRpY19zdGFnZV9pbnB1dF9wcm92ZW5hbmNlJywnYWN0aXZlX3ByaW1hcnlfcHJvY2Vzc19ncmFwaCcsCiAgICAgICAgJ25hdGl2ZV9wcm9jZXNzX2NvbnRleHRfcmV0YWluZWRfYXNfcmV2aXNpb25fbGluZWFnZV9ub3Rfc2Vjb25kX2FjdGl2ZV9ncmFwaCcsCiAgICAgICAgJ3VubGlzdGVkX3Byb3BlcnR5X3Byb2Nlc3NfY29udGV4dHNfcmVtYWluX2FjdGl2ZScsCiAgICAgICAgJ2NvbXBsZXRlX3NlbWFudGljX3NvdXJjZV9zdXBwb3J0X25vdF9jZXJ0aWZpZWRfYnlfc3RydWN0dXJhbF92YWxpZGF0aW9uJ30KICAgIGlmIGlzaW5zdGFuY2UocHJlZGljdGlvbi5nZXQoJ2NvdW50cycpLGRpY3QpIGFuZCBhbGwoaXNpbnN0YW5jZShrLHN0cikgYW5kIHR5cGUodikgaXMgaW50IGFuZCB2Pj0wCiAgICAgICAgICAgIGZvciBrLHYgaW4gcHJlZGljdGlvblsnY291bnRzJ10uaXRlbXMoKSk6CiAgICAgICAgcm9vdF9tZXRhZGF0YS5hZGQoJ2NvdW50cycpCiAgICBmb3IgZmxhZyBpbiAoJ3NvdXJjZV9zZW1hbnRpY19saW5lYWdlX2NvbXBsZXRlJywnZmlyc3RfZ3JhcGhfaWRlbnRpdHlfYW5kX3NvdXJjZV9jaGVja2VkJywKICAgICAgICAgICAgJ2hpc3RvcmljYWxfZmlyc3RfY2FwdHVyZV9wcmlvcml0eV9ub3RfaW5kZXBlbmRlbnRseV9jZXJ0aWZpZWQnKToKICAgICAgICBpZiB0eXBlKHByZWRpY3Rpb24uZ2V0KGZsYWcpKSBpcyBib29sOgogICAgICAgICAgICByb290X21ldGFkYXRhLmFkZChmbGFnKQogICAgcm9vdF9lbnVtZXJhdGVkPXsncHJvY2Vzc19ncmFwaCcsJ3NvdXJjZV9zZW1hbnRpY19ncmFwaCcsJ25hdGl2ZV9wcm9jZXNzX2NvbnRleHQnLCdlZmZlY3RpdmVfcHJvY2Vzc19jb250ZXh0cycsCiAgICAgICAgJ3JlY292ZXJlZF9vcGVyYXRpb25faGlzdG9yeScsJ3BlbmRpbmdfaGlzdG9yeV9yZWNvdmVyeScsJ3VuY29uZmlybWVkX25hdGl2ZV9jbGFpbXNfc3RpbGxfYWN0aXZlX2Zvcl9vdXRwdXRfc3VwcG9ydCd9CiAgICBmb3Iga2V5IGluIHNvcnRlZChzZXQocHJlZGljdGlvbiktcm9vdF9tZXRhZGF0YS1yb290X2VudW1lcmF0ZWQpOgogICAgICAgIHRva2VuPWtleS5yZXBsYWNlKCd+JywnfjAnKS5yZXBsYWNlKCcvJywnfjEnKQogICAgICAgIGFkZCgnLycrdG9rZW4scHJlZGljdGlvbltrZXldLCd1bmNsYXNzaWZpZWRfcm9vdF9leHRlbnNpb24nLAogICAgICAgICAgICBwdWJsaWNhdGlvbj0ndW5jbGFzc2lmaWVkX2V4dGVuc2lvbl9yZXF1aXJlc19zY29wZV9yZXZpZXcnKQogICAgcmV0dXJuIGRpY3QocmVmZXJlbmNlX25vPXByZWRpY3Rpb25bJ3JlZmVyZW5jZV9ubyddLHJldmlld19jb250YWluZXJzPXJvd3MsCiAgICAgICAgY29udGFpbmVyX2NvdW50PWxlbihyb3dzKSxub3RfZmluYWxfZGVkdXBsaWNhdGVkX2ZpdmVfZGltZW5zaW9uX2Rlbm9taW5hdG9ycz1UcnVlLAogICAgICAgIGV2ZXJ5X2NvbnRhaW5lcl9yZXF1aXJlc19zY29wZV9kaXNwb3NpdGlvbj1UcnVlLAogICAgICAgIHdob2xlX2NvbnRhaW5lcl9jb25qdW5jdGlvbl9tYXlfbmVlZF9tdWx0aXBsZV9kaW1lbnNpb25fdW5pdHM9VHJ1ZSwKICAgICAgICBub191bmtub3duX2NsYWltX2F1dG9tYXRpY2FsbHlfZGVsZXRlZD1UcnVlLAogICAgICAgIHJlZmVyZW5jZV9jb3ZlcmFnZT1Ob25lLG91dHB1dF9zb3VyY2Vfc3VwcG9ydD1Ob25lLGV4dGVybmFsX2FwaV9jYWxscz0wKQoKCmRlZiBtYWluKCk6CiAgICByZWplY3Rfb3B0aW1pemVkKCkKICAgIHBhcnNlcj1hcmdwYXJzZS5Bcmd1bWVudFBhcnNlcihkZXNjcmlwdGlvbj1fX2RvY19fKQogICAgcGFyc2VyLmFkZF9hcmd1bWVudCgnLS1wcmVkaWN0aW9uJyx0eXBlPVBhdGgscmVxdWlyZWQ9VHJ1ZSkKICAgIHBhcnNlci5hZGRfYXJndW1lbnQoJy0tb3V0cHV0Jyx0eXBlPVBhdGgscmVxdWlyZWQ9VHJ1ZSkKICAgIGFyZ3M9cGFyc2VyLnBhcnNlX2FyZ3MoKQogICAgaWYgYXJncy5vdXRwdXQuZXhpc3RzKCk6IHJhaXNlIFZhbHVlRXJyb3IoJ0RvIG5vdCByZXBsYWNlIGFuIGV4aXN0aW5nIGludmVudG9yeScpCiAgICByZXN1bHQ9aW52ZW50b3J5KGpzb24ubG9hZHMoYXJncy5wcmVkaWN0aW9uLnJlYWRfdGV4dChlbmNvZGluZz0ndXRmLTgtc2lnJykpKQogICAgcmVzdWx0WydwcmVkaWN0aW9uJ109ZGljdChwYXRoPXN0cihhcmdzLnByZWRpY3Rpb24ucmVzb2x2ZSgpKSwKICAgICAgICBzaGEyNTY9aGFzaGxpYi5zaGEyNTYoYXJncy5wcmVkaWN0aW9uLnJlYWRfYnl0ZXMoKSkuaGV4ZGlnZXN0KCkpCiAgICByZXN1bHRbJ2ludmVudG9yeV9jb2RlX3NoYTI1NiddPWhhc2hsaWIuc2hhMjU2KFBhdGgoX19maWxlX18pLnJlYWRfYnl0ZXMoKSkuaGV4ZGlnZXN0KCkKICAgIGFyZ3Mub3V0cHV0LnBhcmVudC5ta2RpcihwYXJlbnRzPVRydWUsZXhpc3Rfb2s9VHJ1ZSkKICAgIGFyZ3Mub3V0cHV0LndyaXRlX3RleHQoanNvbi5kdW1wcyhyZXN1bHQsZW5zdXJlX2FzY2lpPUZhbHNlLGluZGVudD0yKSsnXG4nLGVuY29kaW5nPSd1dGYtOCcpCiAgICBwcmludChqc29uLmR1bXBzKGRpY3QocmVmZXJlbmNlX25vPXJlc3VsdFsncmVmZXJlbmNlX25vJ10scmV2aWV3X2NvbnRhaW5lcnM9cmVzdWx0Wydjb250YWluZXJfY291bnQnXSwKICAgICAgICBzY2llbnRpZmljX2Rlbm9taW5hdG9yc19ub3RfY2VydGlmaWVkPVRydWUsZXh0ZXJuYWxfYXBpX2NhbGxzPTApLGVuc3VyZV9hc2NpaT1GYWxzZSkpCgoKaWYgX19uYW1lX189PSdfX21haW5fXyc6CiAgICBtYWluKCkK'


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode('utf-8')).hexdigest()


def reject_optimized():
    if sys.flags.optimize:
        raise ValueError('Optimized Python is forbidden')


def pointer(value, path):
    if path == '':
        return value
    if not isinstance(path, str) or not path.startswith('/'):
        raise ValueError('Invalid exact prediction pointer')
    for part in path[1:].split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def _legacy_inventory(prediction):
    raw = base64.b64decode(LEGACY_SOURCE_BASE64)
    if hashlib.sha256(raw).hexdigest() != LEGACY_SOURCE_SHA256:
        raise ValueError('Embedded legacy source hash mismatch')
    tree = ast.parse(raw.decode('utf-8-sig'))
    # The only project import provides an optimize guard, implemented above.
    tree.body = [node for node in tree.body if not
        (isinstance(node, ast.ImportFrom) and node.module == 'evaluation_integrity')]
    namespace = dict(__name__='_embedded_frozen_legacy_inventory',
        __file__=__file__, reject_optimized=reject_optimized)
    exec(compile(tree, '<sha256-bound-legacy-inventory>', 'exec'), namespace)
    return namespace['inventory'](prediction)


def inventory(prediction):
    reject_optimized()
    base = {k: v for k, v in prediction.items() if k not in (COLLECTION, AUDIT)}
    result = _legacy_inventory(base)
    prefix = len(result['review_containers'])
    if COLLECTION not in prediction or AUDIT not in prediction:
        raise ValueError('Native completion collection and audit are required')
    audit = prediction[AUDIT]
    if audit['original_prediction_canonical_sha256'] != canonical(base):
        raise ValueError('Original prediction differs from completion audit')
    seen = set()
    for i, owner in enumerate(prediction[COLLECTION]):
        path = '/' + COLLECTION + '/' + str(i)
        original_path = owner['original_owner_path']
        if original_path in seen:
            raise ValueError('Duplicate additional native owner')
        seen.add(original_path)
        if owner['native_source'] != prediction['property_source'] or owner['native_source'] != audit['native_source']:
            raise ValueError('Native file witness differs')
        kind = owner['record_kind']
        if kind == 'complete_native_owner':
            if canonical(owner['unmodified_original_owner']) != owner['original_owner_sha256']:
                raise ValueError('Native owner copy/hash mismatch')
        elif kind == 'series_parent_nonpoint_context':
            payload = owner['unmodified_original_owner_fields_except_points']
            if 'points' in payload:
                raise ValueError('Series projection includes points')
            expected = {original_path + '/' + str(k).replace('~', '~0').replace('/', '~1'):
                canonical(v) for k, v in payload.items()}
            actual = {r['original_context_path']: r['original_context_sha256']
                for r in owner['original_nonpoint_field_witnesses']}
            if expected != actual or len(actual) != len(owner['original_nonpoint_field_witnesses']):
                raise ValueError('Series field projection witnesses differ')
            if owner['original_points_context']['original_context_path'] != original_path + '/points':
                raise ValueError('Series points pointer differs')
            for j, covered in enumerate(owner['point_owner_coverage']):
                if covered['original_owner_path'] != original_path + '/points/' + str(j):
                    raise ValueError('Missing/reordered series point coverage')
                target = pointer(prediction, covered['prediction_path'])
                if covered['disposition'] in ('already_effective_owner', 'additional_owner_published'):
                    if target.get('original_owner_sha256') != covered['original_owner_sha256']:
                        raise ValueError('Point target hash differs')
                elif canonical(target) != covered['original_owner_sha256']:
                    raise ValueError('Retained native point hash differs')
        else:
            raise ValueError('Unknown native owner record kind')
        row = dict(id='C' + str(prefix + i + 1).zfill(6), prediction_path=path,
            complete_container_sha256=canonical(owner),
            role='additional_native_' + kind, initial_kind_hint=None,
            publication_boundary='native_owner_requires_scope_review', complete_container=owner,
            scope_semantics_and_full_conjunction_not_yet_reviewed=True)
        if pointer(prediction, path) != owner:
            raise ValueError('Container is not an actual prediction object')
        result['review_containers'].append(row)
    result['container_count'] = len(result['review_containers'])
    result['legacy_container_prefix_count'] = prefix
    result['legacy_inventory_source_sha256'] = LEGACY_SOURCE_SHA256
    result['native_owner_completion_contract'] = 'native_owner_runtime_completion_v2'
    result['native_completion_audit_prediction_path'] = '/' + AUDIT
    result['native_completion_audit_sha256'] = canonical(audit)
    result['native_file_hash_revalidation_is_runner_responsibility'] = True
    return result


def main():
    reject_optimized()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prediction', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Do not replace an existing inventory')
    raw = args.prediction.read_bytes()
    result = inventory(json.loads(raw.decode('utf-8-sig')))
    result['prediction'] = dict(path=str(args.prediction.resolve()), sha256=hashlib.sha256(raw).hexdigest())
    result['inventory_code_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(reference_no=result['reference_no'], review_containers=result['container_count'],
        legacy_prefix=result['legacy_container_prefix_count'], external_api_calls=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
