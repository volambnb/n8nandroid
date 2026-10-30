import type {
	ICredentialTestRequest,
	ICredentialType,
	IAuthenticateGeneric,
	INodeProperties,
} from 'n8n-workflow';

export class AutoIxbApi implements ICredentialType {
	name = 'autoIxbApi';
	displayName = 'AutoIXB API';
	properties: INodeProperties[] = [
		{
			displayName: 'Base URL',
			name: 'baseUrl',
			type: 'string',
			default: 'http://127.0.0.1:8000',
			placeholder: 'http://127.0.0.1:8000',
			required: true,
			description:
				'URL where the autoIXB FastAPI service is reachable from the n8n process. Use the Windows host address if n8n runs in Docker.',
			noDataExpression: true,
		},
		{
			displayName: 'Bearer Token',
			name: 'apiToken',
			type: 'string',
			default: '',
			required: false,
			typeOptions: { password: true },
			description: 'Optional only when API_BEARER_TOKEN is blank. Otherwise this must match the autoIXB server token.',
			noDataExpression: true,
		},
	];
	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				Authorization: '=Bearer {{$credentials.apiToken}}',
			},
		},
	};
	test: ICredentialTestRequest = {
		request: {
			baseURL: '={{$credentials.baseUrl}}',
			url: '/automation/catalog',
			method: 'GET',
		},
	};
}
