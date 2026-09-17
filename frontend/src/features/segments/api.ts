import { api } from '../../lib/api';
import { Segment, SegmentCreatePayload } from '../../types';

export const segmentApi = {
  listSegments: async (projectId: string): Promise<Segment[]> => {
    const res = await api.get<Segment[]>(`/api/v1/projects/${projectId}/segments`);
    return res.data;
  },

  createSegment: async (
    projectId: string,
    payload: SegmentCreatePayload
  ): Promise<Segment> => {
    const res = await api.post<Segment>(`/api/v1/projects/${projectId}/segments`, payload);
    return res.data;
  },

  deleteSegment: async (projectId: string, segmentId: string): Promise<void> => {
    await api.delete(`/api/v1/projects/${projectId}/segments/${segmentId}`);
  },
};
